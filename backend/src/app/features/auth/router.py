from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.database import app_sessions
from app.features.auth.schemas import LoginResponse, UserSession

router = APIRouter(tags=["auth"])


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
def login(response: Response, user_id: str) -> LoginResponse:
    app_session_id = str(uuid4())

    app_sessions[app_session_id] = {
        "user_id": user_id,
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
        user_id=user_id,
        message="Logged in",
    )
