from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import BankAccountModel, TransactionModel
from app.features.connections.models import BankConnectionModel


async def upsert_bank_accounts(db: AsyncSession, accounts: list[dict[str, Any]]) -> None:
    if not accounts:
        return
    stmt = insert(BankAccountModel).values(accounts)
    # Balance columns are cache state maintained by sync_account_balance,
    # not part of the connection payload — never let a reconnect clobber
    # them with the NULL defaults of an omitted insert column.
    update_columns = set(BankAccountModel.__table__.columns.keys()) - {
        "account_id",
        "display_name",
        "sort_order",
        "current_balance",
        "available_balance",
        "balance_currency",
        "last_synced_at",
        "sync_status",
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id"],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    await db.execute(stmt)
    await db.commit()


async def get_for_connection(db: AsyncSession, connection_id: UUID) -> list[BankAccountModel]:
    result = await db.execute(
        select(BankAccountModel)
        .where(BankAccountModel.connection_id == connection_id)
        .order_by(
            BankAccountModel.sort_order.is_(None),
            BankAccountModel.sort_order,
            BankAccountModel.name,
        )
    )
    return list(result.scalars().all())


async def get_account_owned_by_user(
    db: AsyncSession, user_id: str, account_id: str
) -> BankAccountModel | None:
    result = await db.execute(
        select(BankAccountModel)
        .join(
            BankConnectionModel, BankAccountModel.connection_id == BankConnectionModel.connection_id
        )
        .where(BankAccountModel.account_id == account_id, BankConnectionModel.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_customizations_by_iban(db: AsyncSession, user_id: str) -> dict[str, dict[str, Any]]:
    # Enable Banking's account_id (uid) isn't stable across a bank
    # reconnect — a fresh authorization mints new uids for the same
    # physical accounts. iban is the actually-stable identity, so
    # rename/reorder gets carried forward by matching on it.
    result = await db.execute(
        select(BankAccountModel.iban, BankAccountModel.display_name, BankAccountModel.sort_order)
        .join(
            BankConnectionModel, BankAccountModel.connection_id == BankConnectionModel.connection_id
        )
        .where(
            BankConnectionModel.user_id == user_id,
            BankAccountModel.iban.is_not(None),
            or_(
                BankAccountModel.display_name.is_not(None),
                BankAccountModel.sort_order.is_not(None),
            ),
        )
        .order_by(BankConnectionModel.created_at.desc())
    )
    customizations: dict[str, dict[str, Any]] = {}
    for iban, display_name, sort_order in result.all():
        if iban not in customizations:
            customizations[iban] = {"display_name": display_name, "sort_order": sort_order}
    return customizations


async def get_all_owned_by_user(db: AsyncSession, user_id: str) -> list[BankAccountModel]:
    result = await db.execute(
        select(BankAccountModel)
        .join(
            BankConnectionModel, BankAccountModel.connection_id == BankConnectionModel.connection_id
        )
        .where(BankConnectionModel.user_id == user_id)
    )
    return list(result.scalars().all())


async def set_sort_orders(db: AsyncSession, ordered_account_ids: list[str]) -> None:
    for index, account_id in enumerate(ordered_account_ids):
        account = await db.get(BankAccountModel, account_id)
        if account is not None:
            account.sort_order = index
    await db.commit()


async def set_display_name(db: AsyncSession, account_id: str, display_name: str | None) -> None:
    account = await db.get(BankAccountModel, account_id)
    if account is None:
        return
    account.display_name = display_name
    await db.commit()


async def get_account_for_connection(
    db: AsyncSession, connection_id: UUID, account_id: str
) -> BankAccountModel | None:
    result = await db.execute(
        select(BankAccountModel).where(
            BankAccountModel.connection_id == connection_id,
            BankAccountModel.account_id == account_id,
        )
    )
    return result.scalar_one_or_none()


async def get_transaction_by_id(
    db: AsyncSession, account_id: str, transaction_id: str
) -> TransactionModel | None:
    result = await db.execute(
        select(TransactionModel).where(
            TransactionModel.account_id == account_id,
            TransactionModel.transaction_id == transaction_id,
        )
    )
    return result.scalar_one_or_none()


async def get_transactions_for_account(db: AsyncSession, account_id: str) -> list[TransactionModel]:
    result = await db.execute(
        select(TransactionModel)
        .where(TransactionModel.account_id == account_id)
        .order_by(TransactionModel.booking_date.desc(), TransactionModel.value_date.desc())
    )
    return list(result.scalars().all())


async def get_transactions_for_accounts_since(
    db: AsyncSession, account_ids: list[str], since: date
) -> list[TransactionModel]:
    if not account_ids:
        return []
    result = await db.execute(
        select(TransactionModel)
        .where(
            TransactionModel.account_id.in_(account_ids),
            # Pending transactions often carry no booking_date yet — a
            # NULL never satisfies `>= since` in SQL, so it has to be
            # let through explicitly or it silently vanishes from view.
            or_(
                TransactionModel.booking_date >= since,
                TransactionModel.booking_date.is_(None),
            ),
        )
        .order_by(TransactionModel.booking_date.desc(), TransactionModel.value_date.desc())
    )
    return list(result.scalars().all())


async def update_account_balance(
    db: AsyncSession,
    account_id: str,
    sync_status: str,
    current_balance: Decimal | None = None,
    available_balance: Decimal | None = None,
    balance_currency: str | None = None,
    last_synced_at: datetime | None = None,
) -> None:
    account = await db.get(BankAccountModel, account_id)
    if account is None:
        return
    account.sync_status = sync_status
    if last_synced_at is not None:
        account.last_synced_at = last_synced_at
        account.current_balance = current_balance
        account.available_balance = available_balance
        account.balance_currency = balance_currency
    await db.commit()

async def upsert_many(db: AsyncSession, transactions: list[dict[str, Any]]) -> None:
    if not transactions:
        return
    stmt = insert(TransactionModel).values(transactions)
    update_columns = set(TransactionModel.__table__.columns.keys()) - {
        "id", "account_id", "transaction_id"
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id", "transaction_id"],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    await db.execute(stmt)
    await db.commit()

