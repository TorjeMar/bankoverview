from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StartAuthorizationResponse(BaseModel):
    authorization_url: str


class BankConnection(BaseModel):
    user_id: str
    enable_banking_session_id: str
    status: str
    created_at: datetime
    valid_until: datetime | None = None
    aspsp: dict[str, Any] | None = None
    account_metadata: list[dict[str, Any]] = Field(default_factory=list)


class BankConnectionResponse(BaseModel):
    status: str
    created_at: datetime
    valid_until: datetime | None = None
    aspsp: dict[str, Any] | None = None
    account_count: int


class CallbackResponse(BaseModel):
    message: str
    connection: BankConnectionResponse


class AccountsResponse(BaseModel):
    accounts: list[dict[str, Any]] = Field(default_factory=list)
