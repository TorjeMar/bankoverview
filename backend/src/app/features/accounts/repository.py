from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import BankAccountModel, TransactionModel


async def save_many_bank_accounts(db: AsyncSession, accounts: list[BankAccountModel]) -> None:
    db.add_all(accounts)
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
