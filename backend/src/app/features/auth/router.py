from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.core.config import settings
from app.database import get_db
from app.features.auth import repository
from app.features.auth.schemas import UserSession

router = APIRouter(tags=["auth"])

SESSION_MAX_AGE = timedelta(days=7)

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    client_kwargs={"scope": "openid email profile"},
)


def get_current_user(
    session_token: Annotated[str | None, Cookie()] = None,
) -> UserSession:
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session cookie",
        )

    try:
        payload = jwt.decode(session_token, settings.session_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        ) from exc

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session does not contain a valid user",
        )

    return UserSession(user_id=user_id)


@router.get("/login", summary="Start Google login")
async def login(request: Request) -> RedirectResponse:
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get(
    "/login/callback",
    name="auth_callback",
    summary="Handle Google login callback",
)
async def auth_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")

    if userinfo is None or not userinfo.get("sub") or not userinfo.get("email"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google did not return the expected user info",
        )

    user = await repository.get_or_create_user_by_google_subject(
        db, subject=userinfo["sub"], email=userinfo["email"]
    )

    session_token = jwt.encode(
        {
            "user_id": str(user.user_id),
            "exp": datetime.now(UTC) + SESSION_MAX_AGE,
        },
        settings.session_secret,
        algorithm="HS256",
    )

    # The cookie has to be set on the object we actually return — setting
    # it on an injected `response: Response` parameter only works if the
    # endpoint doesn't return its own Response instance directly.
    redirect_response = RedirectResponse(url="/dev/")
    redirect_response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=int(SESSION_MAX_AGE.total_seconds()),
    )

    return redirect_response
