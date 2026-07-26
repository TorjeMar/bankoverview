from datetime import datetime

from pydantic import BaseModel


class LoginResponse(BaseModel):
    message: str
    user_id: str


class UserSession(BaseModel):
    user_id: str
    app_session_id: str


class PendingAuthorization(BaseModel):
    user_id: str
    app_session_id: str
    created_at: datetime
    status: str
