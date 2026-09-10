from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.accounts import repository
from app.features.accounts.models import TransactionModel
from app.features.accounts.schemas import (
    AccountBalanceResponse,
    AccountDetailsResponse,
    AccountsResponse,
    AccountTransactionResponse,
    AccountTransactionsResponse,
)
from app.integrations.enable_banking.client import (
    retrieve_account_balances,
    retrieve_account_transactions,
)
from app.integrations.enable_banking.schemas import (
    EnableBankingAccount,
    EnableBankingBalance,
    EnableBankingTransaction,
    RetrievedEnableBankingSession,
)


def to_get_accounts_response(session: RetrievedEnableBankingSession) -> AccountsResponse:
    return AccountsResponse(
        accounts=session.accounts,
    )

def to_account_details_response(account: EnableBankingAccount) -> AccountDetailsResponse:
    return AccountDetailsResponse(
        account_id=account.account_id.model_dump(),
        all_account_ids=[
            identifier.model_dump() for identifier in (account.all_account_ids or [])
        ],
        account_servicer=(
            account.account_servicer.model_dump() if account.account_servicer else None
        ),
        name=account.name,
        details=account.details,
        usage=account.usage,
        cash_account_type=account.cash_account_type,
        product=account.product,
        currency=account.currency,
        credit_limit=account.credit_limit,
        postal_address=account.postal_address,
        uid=account.uid,
        identification_hash=account.identification_hash,
        identification_hashes=account.identification_hashes,
    )

def to_account_balance_response(
    account_id: str, balance: EnableBankingBalance
) -> AccountBalanceResponse:
    return AccountBalanceResponse(
        account_id=account_id,
        balances=balance.balances or []
    )

def to_account_transactions_response(
    account_id: str, transactions: list[TransactionModel]
) -> AccountTransactionsResponse:
    return AccountTransactionsResponse(
        account_id=account_id,
        transactions=[
            {
                "transaction_id": t.transaction_id,
                "amount": t.amount,
                "currency": t.currency,
                "credit_debit_indicator": t.credit_debit_indicator,
                "status": t.status,
                "booking_date": t.booking_date,
                "value_date": t.value_date,
                "remittance_information": t.remittance_information,
            }
            for t in transactions
        ],
    )

def to_account_transaction_response(
    account_id: str, transaction: EnableBankingTransaction
) -> AccountTransactionResponse:
    return AccountTransactionResponse(
        account_id=account_id,
        entry_reference=transaction.entry_reference,
        merchant_category_code=transaction.merchant_category_code,
        transaction_amount=transaction.transaction_amount,
        creditor=transaction.creditor,
        creditor_account=transaction.creditor_account,
        creditor_agent=transaction.creditor_agent,
        debtor=transaction.debtor,
        debtor_account=transaction.debtor_account,
        debtor_agent=transaction.debtor_agent,
        bank_transaction_code=transaction.bank_transaction_code,
        credit_debit_indicator=transaction.credit_debit_indicator,
        status=transaction.status,
        booking_date=transaction.booking_date,
        value_date=transaction.value_date,
        transaction_date=transaction.transaction_date,
        balance_after_transaction=transaction.balance_after_transaction,
        refrence_number=transaction.refrence_number,
        refrence_number_schema=transaction.refrence_number_schema,
        remittance_information=transaction.remittance_information,
        debtor_account_additional_identification=transaction.debtor_account_additional_identification,
        creditor_account_additional_identification=transaction.creditor_account_additional_identification
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