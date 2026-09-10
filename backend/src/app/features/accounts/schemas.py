from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class AccountsResponse(BaseModel):
    accounts: list[str] = Field(default_factory=list)


class RenameAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)


class RenameAccountResponse(BaseModel):
    account_id: str
    display_name: str | None = None


class ReorderAccountsRequest(BaseModel):
    account_ids: list[str]

class AccountDetailsResponse(BaseModel):
    account_id: dict[str, Any] = Field(default_factory=dict)
    all_account_ids: list[dict[str, Any]] = Field(default_factory=list)
    account_servicer: dict[str, Any] | None = None
    name: str | None = None
    details: str | None = None
    usage: str | None = None
    cash_account_type: str | None = None
    product: str | None = None
    currency: str | None = None
    credit_limit: Any | None = None
    postal_address: Any | None = None
    uid: str | None = None
    identification_hash: str | None = None
    identification_hashes: list[str] = Field(default_factory=list)

class AccountBalanceResponse(BaseModel):
    account_id: str | None = None
    balances: list[dict[str, Any]] = Field(default_factory=list)


class AccountTransactionsResponse(BaseModel):
    account_id: str | None = None
    transactions: list[dict[str, Any]] = Field(default_factory=list)


class AccountTransactionResponse(BaseModel):
    account_id: str | None = None
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
    remittance_information: list[str] | None = None
    debtor_account_additional_identification: dict[str, Any] | None = None
    creditor_account_additional_identification: dict[str, Any] | None = None
    exchange_rate: dict[str, Any] | None = None
    note: str | None = None
    transaction_id: str | None = None