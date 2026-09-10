from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import requests
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts import repository as accounts_repository
from app.features.accounts.service import sync_account_balance, sync_transactions_for_account
from app.features.connections import repository as connections_repository
from app.features.connections.models import BankConnectionModel
from app.features.overview.schemas import (
    CurrencyTotal,
    OverviewAccount,
    OverviewConnection,
    OverviewResponse,
    OverviewTransaction,
    PartialFailure,
    SyncResponse,
)


async def build_overview(
    db: AsyncSession, connections: list[BankConnectionModel], days: int
) -> OverviewResponse:
    since = date.today() - timedelta(days=days)

    overview_accounts = []
    overview_transactions = []
    overview_connections = []
    partial_failures = []
    balance_by_currency: dict[str, Decimal] = {}
    inflow_by_currency: dict[str, Decimal] = {}
    outflow_by_currency: dict[str, Decimal] = {}

    for connection in connections:
        bank = await connections_repository.get_bank_by_id(db, connection.bank_id)
        bank_name = bank.name if bank else ""
        accounts = await accounts_repository.get_for_connection(db, connection.connection_id)
        transactions = await accounts_repository.get_transactions_for_accounts_since(
            db, [account.account_id for account in accounts], since
        )

        for account in accounts:
            # Bank balances don't reflect a transaction until it's booked —
            # a still-pending debit hasn't left the reported balance yet.
            # Apply it ourselves so the shown balance already accounts for
            # money that's effectively gone; if the pending transaction
            # later drops out of a re-sync (reversed/cancelled), this
            # recomputes from scratch and the adjustment disappears with it.
            pending = _pending_adjustment(transactions, account.account_id)
            current_balance = (
                account.current_balance + pending if account.current_balance is not None else None
            )
            available_balance = (
                account.available_balance + pending
                if account.available_balance is not None
                else None
            )

            balances = []
            if current_balance is not None:
                balances.append(
                    {
                        "balance_type": "CLBD",
                        "balance_amount": {
                            "amount": str(current_balance),
                            "currency": account.balance_currency,
                        },
                    }
                )
            if available_balance is not None:
                balances.append(
                    {
                        "balance_type": "ITAV",
                        "balance_amount": {
                            "amount": str(available_balance),
                            "currency": account.balance_currency,
                        },
                    }
                )

            overview_accounts.append(
                OverviewAccount(
                    account_id=account.account_id,
                    connection_id=str(connection.connection_id),
                    bank_name=bank_name,
                    name=account.display_name or account.name,
                    iban=account.iban,
                    cash_account_type=account.cash_account_type,
                    currency=account.currency,
                    balance_currency=account.balance_currency,
                    current_balance=current_balance,
                    balances=balances,
                    last_synced_at=account.last_synced_at,
                    sync_status=account.sync_status,
                )
            )

            if account.sync_status == "error":
                partial_failures.append(
                    PartialFailure(account_id=account.account_id, name=account.name)
                )

            if account.balance_currency and current_balance is not None:
                balance_by_currency[account.balance_currency] = (
                    balance_by_currency.get(account.balance_currency, Decimal(0))
                    + current_balance
                )

        status = connection.status
        if (
            status == "active"
            and connection.valid_until is not None
            and connection.valid_until < datetime.now(UTC)
        ):
            status = "expired"

        overview_connections.append(
            OverviewConnection(
                connection_id=str(connection.connection_id),
                status=status,
                bank_name=bank_name,
                bank_country=bank.country_code if bank else "",
                created_at=connection.created_at,
                valid_until=connection.valid_until,
                account_count=len(accounts),
            )
        )

        overview_transactions.extend(_build_overview_transactions(transactions))
        _accumulate_flows(transactions, inflow_by_currency, outflow_by_currency)

    return OverviewResponse(
        accounts=overview_accounts,
        transactions=overview_transactions,
        connections=overview_connections,
        currency_totals=_currency_totals(
            balance_by_currency, inflow_by_currency, outflow_by_currency
        ),
        partial_failures=partial_failures,
    )


def _pending_adjustment(transactions: list, account_id: str) -> Decimal:
    total = Decimal(0)
    for transaction in transactions:
        if transaction.account_id != account_id or transaction.status != "PDNG":
            continue
        # Enable Banking tags some still-processing transfers "XXX" (no
        # currency assigned yet) even though the amount is already in the
        # account's own currency and already reflected in the bank's own
        # real-time balance — confirmed against the actual bank balance, so
        # don't exclude it here (unlike the cross-account currency-totals
        # grouping, where the real currency genuinely isn't knowable yet).
        if transaction.credit_debit_indicator == "CRDT":
            total += transaction.amount
        else:
            total -= transaction.amount
    return total


def _build_overview_transactions(transactions: list) -> list[OverviewTransaction]:
    return [
        OverviewTransaction(
            account_id=transaction.account_id,
            transaction_id=transaction.transaction_id,
            amount=transaction.amount,
            currency=transaction.currency,
            credit_debit_indicator=transaction.credit_debit_indicator,
            status=transaction.status,
            booking_date=transaction.booking_date,
            remittance_information=transaction.remittance_information,
        )
        for transaction in transactions
    ]


def _accumulate_flows(
    transactions: list,
    inflow_by_currency: dict[str, Decimal],
    outflow_by_currency: dict[str, Decimal],
) -> None:
    for transaction in transactions:
        # ISO 4217 "XXX" = no currency — Enable Banking sends this on some
        # still-pending transfers before the bank settles a real currency.
        # Not real money in any currency yet; would otherwise spawn a bogus
        # "XXX" card in the totals.
        if transaction.currency == "XXX":
            continue
        # Bank's own label for a transfer between the user's own accounts —
        # real money moved, but not real income/spending; would otherwise
        # double-count on both legs and inflate both In and Out.
        if "kontoregulering" in transaction.remittance_information.lower():
            continue
        if transaction.credit_debit_indicator == "CRDT":
            inflow_by_currency[transaction.currency] = (
                inflow_by_currency.get(transaction.currency, Decimal(0)) + transaction.amount
            )
        else:
            outflow_by_currency[transaction.currency] = (
                outflow_by_currency.get(transaction.currency, Decimal(0)) + transaction.amount
            )


def _currency_totals(
    balance_by_currency: dict[str, Decimal],
    inflow_by_currency: dict[str, Decimal],
    outflow_by_currency: dict[str, Decimal],
) -> list[CurrencyTotal]:
    currencies = set(balance_by_currency) | set(inflow_by_currency) | set(outflow_by_currency)
    totals = [
        CurrencyTotal(
            currency=currency,
            balance=balance_by_currency.get(currency, Decimal(0)),
            inflow=inflow_by_currency.get(currency, Decimal(0)),
            outflow=outflow_by_currency.get(currency, Decimal(0)),
            net=(
                inflow_by_currency.get(currency, Decimal(0))
                - outflow_by_currency.get(currency, Decimal(0))
            ),
        )
        for currency in currencies
    ]
    totals.sort(key=lambda total: total.balance, reverse=True)
    return totals


async def sync_connections(
    db: AsyncSession, connections: list[BankConnectionModel]
) -> SyncResponse:
    failures = []
    accounts_synced = 0
    transactions_synced = 0

    for connection in connections:
        accounts = await accounts_repository.get_for_connection(db, connection.connection_id)
        for account in accounts:
            try:
                await sync_account_balance(db, account.account_id)
                transactions_synced += await sync_transactions_for_account(
                    db, account.account_id, since=date.today() - timedelta(days=7)
                )
                accounts_synced += 1
            except (requests.RequestException, ValidationError):
                await accounts_repository.update_account_balance(
                    db, account.account_id, sync_status="error"
                )
                failures.append(PartialFailure(account_id=account.account_id, name=account.name))

    return SyncResponse(
        accounts_synced=accounts_synced,
        transactions_synced=transactions_synced,
        failed=failures,
    )
