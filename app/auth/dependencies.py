from typing import Annotated

from fastapi import Cookie, HTTPException, status

from app.auth.types import UserSession
from app.storage.memory import app_sessions


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
