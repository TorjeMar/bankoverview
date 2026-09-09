from pydantic import BaseModel


class UserSession(BaseModel):
    user_id: str
