from datetime import datetime

from pydantic import BaseModel


class LoginResponse(BaseModel):
    message: str
    user_id: str


class UserSession(BaseModel):
    user_id: str
    app_session_id: str
