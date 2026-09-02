from datetime import datetime

from pydantic import BaseModel


class StartAuthorizationResponse(BaseModel):
    authorization_url: str


class PendingAuthorization(BaseModel):
    user_id: str
    app_session_id: str
    created_at: datetime
    status: str


class BankConnectionResponse(BaseModel):
    status: str
    created_at: datetime
    valid_until: datetime | None = None
    account_count: int


class CallbackResponse(BaseModel):
    message: str
    connection: BankConnectionResponse