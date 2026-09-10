from datetime import datetime

from pydantic import BaseModel


class BankOption(BaseModel):
    name: str
    country: str


class StartAuthorizationRequest(BaseModel):
    bank_name: str | None = None
    bank_country: str | None = None


class StartAuthorizationResponse(BaseModel):
    authorization_url: str


class PendingAuthorization(BaseModel):
    user_id: str
    created_at: datetime
    status: str
    bank_name: str
    bank_country: str


class BankConnectionResponse(BaseModel):
    connection_id: str
    status: str
    created_at: datetime
    valid_until: datetime | None = None
    account_count: int


class CallbackResponse(BaseModel):
    message: str
    connection: BankConnectionResponse