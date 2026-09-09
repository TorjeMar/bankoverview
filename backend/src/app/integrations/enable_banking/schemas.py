from datetime import date, datetime
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

class EnableBankingTransaction(BaseModel):
    model_config = ConfigDict(extra="allow")

    entry_reference: str
    merchant_category_code: str | None = None
    transaction_amount: dict[str, Any]
    creditor: dict[str, Any] | None = None
    creditor_account: dict[str, Any] | None = None
    creditor_agent: dict[str, Any] | None = None
    debtor: dict[str, Any] | None = None
    debtor_account: dict[str, Any] | None = None
    debtor_agent: dict[str, Any] | None = None
    bank_transaction_code: dict[str, Any] | None = None
    credit_debit_indicator: str | None = None
    status: str | None = None
    booking_date: date | None = None
    value_date: date | None = None
    transaction_date: date | None = None
    balance_after_transaction: dict[str, Any] | None = None
    refrence_number: str | None = None
    refrence_number_schema: str | None = None
    remittance_information: list | None = None
    debtor_account_additional_identification: dict[str, Any] | None = None
    creditor_account_additional_identification: dict[str, Any] | None = None
    exchange_rate: dict[str, Any] | None = None
    note: str | None = None
    transaction_id: str | None = None


class CreatedEnableBankingSession(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    accounts: list[EnableBankingAccount] = Field(default_factory=list)
    aspsp: dict[str, Any] | None = None
    access: EnableBankingAccess | None = None


class RetrievedEnableBankingSession(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    accounts: list[str] = Field(default_factory=list)
    aspsp: dict[str, Any] | None = None