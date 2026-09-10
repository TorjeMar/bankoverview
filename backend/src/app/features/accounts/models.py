from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("account_id", "transaction_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[str] = mapped_column(ForeignKey("bank_accounts.account_id"))
    transaction_id: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric)
    currency: Mapped[str]
    credit_debit_indicator: Mapped[str]
    status: Mapped[str]
    booking_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    remittance_information: Mapped[str]
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    

class BankAccountModel(Base):
    __tablename__ = "bank_accounts"

    account_id: Mapped[str] = mapped_column(primary_key=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("bank_connections.connection_id"))
    iban: Mapped[str | None] = mapped_column(nullable=True)
    name: Mapped[str | None] = mapped_column(nullable=True)
    display_name: Mapped[str | None] = mapped_column(nullable=True)
    currency: Mapped[str]
    cash_account_type: Mapped[str | None] = mapped_column(nullable=True)
    bic: Mapped[str | None] = mapped_column(nullable=True)
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    available_balance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    balance_currency: Mapped[str | None] = mapped_column(nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str | None] = mapped_column(nullable=True)
    sort_order: Mapped[int | None] = mapped_column(nullable=True)