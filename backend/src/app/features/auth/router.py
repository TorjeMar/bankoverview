import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.core.config import settings
from app.core.csrf import generate_csrf_token
from app.database import get_db
from app.features.auth import repository
from app.features.auth.schemas import MeResponse, UserSession

router = APIRouter(tags=["auth"])

SESSION_MAX_AGE = timedelta(days=7)


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = int(SESSION_MAX_AGE.total_seconds())
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
        max_age=max_age,
    )

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    client_kwargs={"scope": "openid email profile"},
)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
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
    sid = payload.get("sid")

    if not user_id or not sid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session does not contain a valid user",
        )

    session = await repository.get_session(db, UUID(sid))
    if session is not None and session.expires_at < datetime.now(UTC):
        # Opportunistic cleanup — nothing else purges expired rows.
        await repository.delete_session(db, UUID(sid))
        session = None
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired",
        )

    return UserSession(user_id=user_id, session_id=sid)


def verify_csrf(
    current_user: Annotated[UserSession, Depends(get_current_user)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    expected = generate_csrf_token(current_user.session_id)

    if not x_csrf_token or not hmac.compare_digest(expected, x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid CSRF token",
        )


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

    now = datetime.now(UTC)
    session = await repository.create_session(
        db, user_id=user.user_id, expires_at=now + SESSION_MAX_AGE, created_at=now
    )
    sid = str(session.session_id)

    session_token = jwt.encode(
        {
            "user_id": str(user.user_id),
            "sid": sid,
            "exp": now + SESSION_MAX_AGE,
        },
        settings.session_secret,
        algorithm="HS256",
    )

    # The cookie has to be set on the object we actually return — setting
    # it on an injected `response: Response` parameter only works if the
    # endpoint doesn't return its own Response instance directly.
    redirect_response = RedirectResponse(url="/app/")
    _set_session_cookies(redirect_response, session_token, generate_csrf_token(sid))

    return redirect_response


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    dependencies=[Depends(verify_csrf)],
)
async def logout(
    current_user: Annotated[UserSession, Depends(get_current_user)],
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await repository.delete_session(db, UUID(current_user.session_id))

    response.delete_cookie("session_token", path="/")
    response.delete_cookie("csrf_token", path="/")


@router.get("/me", summary="Get the current user")
async def me(
    current_user: Annotated[UserSession, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeResponse:
    user = await repository.get_user_by_id(db, UUID(current_user.user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    return MeResponse(user_id=str(user.user_id), email=user.email)
