from typing import Annotated
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import app_sessions, get_db
from app.features.auth import repository
from app.features.auth.schemas import LoginResponse, UserSession

router = APIRouter(tags=["auth"])

# Fixed, arbitrary namespace for deriving a stable user UUID from whatever
# string /login is given. There's no real registration system yet — this
# lets the same login string always resolve to the same database user
# without adding a separate lookup column.
_USER_ID_NAMESPACE = UUID("d2e5a936-3f0a-4a3b-9f0e-6a8e2c9b7a10")


def derive_user_id(raw_user_id: str) -> UUID:
    return uuid5(_USER_ID_NAMESPACE, raw_user_id)


def get_current_user(
    app_session_id: Annotated[str | None, Cookie()] = None,
) -> UserSession:
    if app_session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing app session cookie",
        )

    session = app_sessions.get(app_session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired app session",
        )

    user_id = session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="App session does not contain a valid user",
        )

    return UserSession(
        user_id=user_id,
        app_session_id=app_session_id,
    )


@router.post("/login", response_model=LoginResponse, summary="Log in and start a session")
async def login(
    response: Response,
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    real_user_id = derive_user_id(user_id)
    await repository.get_or_create_user(db, real_user_id)

    app_session_id = str(uuid4())

    app_sessions[app_session_id] = {
        "user_id": str(real_user_id),
    }

    response.set_cookie(
        key="app_session_id",
        value=app_session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return LoginResponse(
        user_id=str(real_user_id),
        message="Logged in",
    )
