from uuid import uuid4

from fastapi import APIRouter, Response

from app.auth.types import LoginResponse
from app.storage.memory import app_sessions

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
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
