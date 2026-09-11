from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnableBankingAccess(BaseModel):
    model_config = ConfigDict(extra="allow")

    valid_until: datetime | None = None


class AccountIdentifier(BaseModel):
    model_config = ConfigDict(extra="allow")

    identification: str
    scheme_name: str
    issuer: str | None = None


class OtherAccountIdentifier(BaseModel):
    model_config = ConfigDict(extra="allow")

    identification: str
    scheme_name: str
    issuer: str | None = None


class AccountId(BaseModel):
    model_config = ConfigDict(extra="allow")

    iban: str | None = None
    other: OtherAccountIdentifier | None = None


class AccountServicer(BaseModel):
    model_config = ConfigDict(extra="allow")

    bic_fi: str | None = None
    clearing_system_member_id: str | None = None
    name: str | None = None


class EnableBankingAccount(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_id: AccountId
    all_account_ids: list[AccountIdentifier] | None = None
    account_servicer: AccountServicer | None = None

    name: str | None = None
    details: str | None = None
    usage: str | None = None
    cash_account_type: str | None = None
    product: str | None = None
    currency: str
    psu_status: str | None = None
    credit_limit: Any | None = None
    legal_age: Any | None = None
    postal_address: Any | None = None

    uid: str
    identification_hash: str | None = None
    identification_hashes: list[str] = Field(default_factory=list)

class EnableBankingBalance(BaseModel):
    model_config = ConfigDict(extra="allow")

    balances: list[dict[str, Any]] | None = None

class EnableBankingTransactions(BaseModel):
    model_config = ConfigDict(extra="allow")

    transactions: list[dict[str, Any]] | None = None
    continuation_key: str | None = None

class CreatedEnableBankingSession(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    accounts: list[EnableBankingAccount] = Field(default_factory=list)
    aspsp: dict[str, Any] | None = None
    access: EnableBankingAccess | None = None