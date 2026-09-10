from pydantic import BaseModel


class UserSession(BaseModel):
    user_id: str
    session_id: str


class MeResponse(BaseModel):
    user_id: str
    email: str | None
