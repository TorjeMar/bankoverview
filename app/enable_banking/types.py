from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EnableBankingAccess(BaseModel):
    valid_until: datetime | None = None


class EnableBankingSession(BaseModel):
    session_id: str
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    aspsp: dict[str, Any] | None = None
    access: EnableBankingAccess | None = None
