from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.accounts import repository
from app.integrations.enable_banking.client import (
    retrieve_account_balances,
    retrieve_account_transactions,
)


def to_transaction_model(account_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    amount = raw["transaction_amount"]
    return {
        "account_id": account_id,
        "transaction_id": raw["transaction_id"],
        "amount": Decimal(amount["amount"]),
        "currency": amount["currency"],
        "credit_debit_indicator": raw["credit_debit_indicator"],
        "status": raw["status"],
        "booking_date": (
            date.fromisoformat(raw["booking_date"]) if raw.get("booking_date") else None
        ),
        "value_date": date.fromisoformat(raw["value_date"]) if raw.get("value_date") else None,
        "remittance_information": " / ".join(raw.get("remittance_information") or []),
        "details": raw,
    }

async def sync_account_balance(db: AsyncSession, account_id: str) -> None:
    balance = retrieve_account_balances(settings=settings, account_id=account_id)
    by_type = {b.get("balance_type"): b for b in (balance.balances or [])}
    booked = next((by_type[t] for t in ("CLBD", "ITBD") if t in by_type), None)
    available = next((by_type[t] for t in ("ITAV", "CLAV") if t in by_type), None)
    if booked is None:
        booked = available or (balance.balances[0] if balance.balances else None)

    booked_amount = (booked or {}).get("balance_amount") or {}
    available_amount = (available or {}).get("balance_amount") or {}

    await repository.update_account_balance(
        db,
        account_id,
        sync_status="ok",
        current_balance=Decimal(booked_amount["amount"]) if booked_amount.get("amount") else None,
        available_balance=(
            Decimal(available_amount["amount"]) if available_amount.get("amount") else None
        ),
        balance_currency=booked_amount.get("currency"),
        last_synced_at=datetime.now(UTC),
    )


async def sync_transactions_for_account(
    db: AsyncSession, account_id: str, since: date | None = None
) -> int:
    continuation_key = None
    synced = 0
    while True:
        page = retrieve_account_transactions(
            settings=settings,
            account_id=account_id,
            continuation_key=continuation_key,
            date_from=since,
        )
        rows = [to_transaction_model(account_id, t) for t in (page.transactions or [])]
        await repository.upsert_many(db, rows)
        synced += len(rows)
        if not page.continuation_key:
            break
        continuation_key = page.continuation_key
    return synced
