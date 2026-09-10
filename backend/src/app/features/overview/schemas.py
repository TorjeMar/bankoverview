from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class OverviewAccount(BaseModel):
    account_id: str
    connection_id: str
    bank_name: str
    name: str | None = None
    iban: str | None = None
    cash_account_type: str | None = None
    currency: str
    balance_currency: str | None = None
    current_balance: Decimal | None = None
    balances: list[dict[str, Any]]
    last_synced_at: datetime | None = None
    sync_status: str | None = None


class OverviewTransaction(BaseModel):
    account_id: str
    transaction_id: str
    amount: Decimal
    currency: str
    credit_debit_indicator: str
    status: str
    booking_date: date | None = None
    remittance_information: str


class OverviewConnection(BaseModel):
    connection_id: str
    status: str
    bank_name: str
    bank_country: str
    created_at: datetime
    valid_until: datetime | None = None
    account_count: int


class CurrencyTotal(BaseModel):
    currency: str
    balance: Decimal
    inflow: Decimal
    outflow: Decimal
    net: Decimal


class PartialFailure(BaseModel):
    account_id: str
    name: str | None = None


class OverviewResponse(BaseModel):
    accounts: list[OverviewAccount]
    transactions: list[OverviewTransaction]
    connections: list[OverviewConnection]
    currency_totals: list[CurrencyTotal]
    partial_failures: list[PartialFailure]


class SyncResponse(BaseModel):
    accounts_synced: int
    transactions_synced: int
    failed: list[PartialFailure]
