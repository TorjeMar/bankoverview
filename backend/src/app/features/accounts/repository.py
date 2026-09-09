from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import BankAccountModel, TransactionModel


async def upsert_bank_accounts(db: AsyncSession, accounts: list[dict[str, Any]]) -> None:
    if not accounts:
        return
    stmt = insert(BankAccountModel).values(accounts)
    update_columns = set(BankAccountModel.__table__.columns.keys()) - {"account_id"}
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id"],
        set_={col: stmt.excluded[col] for col in update_columns},
    )
    await db.execute(stmt)
    await db.commit()


async def get_for_connection(db: AsyncSession, connection_id: UUID) -> list[BankAccountModel]:
    result = await db.execute(
        select(BankAccountModel).where(BankAccountModel.connection_id == connection_id)
    )
    return list(result.scalars().all())


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
        select(TransactionModel).where(TransactionModel.account_id == account_id)
    )
    return list(result.scalars().all())

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

