from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.connections.models import BankConnectionModel, BankModel


async def save(db: AsyncSession, connection: BankConnectionModel) -> BankConnectionModel:
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


async def get_active_for_user(db: AsyncSession, user_id: str) -> BankConnectionModel | None:
    result = await db.execute(
        select(BankConnectionModel)
        .where(
            BankConnectionModel.user_id == user_id,
            BankConnectionModel.status == "active",
        )
        .order_by(BankConnectionModel.created_at.desc())
    )
    return result.scalars().first()


async def get_all_active_for_user(db: AsyncSession, user_id: str) -> list[BankConnectionModel]:
    result = await db.execute(
        select(BankConnectionModel)
        .where(
            BankConnectionModel.user_id == user_id,
            BankConnectionModel.status == "active",
        )
        .order_by(BankConnectionModel.created_at.desc())
    )
    return list(result.scalars().all())


async def get_by_id_for_user(
    db: AsyncSession, user_id: str, connection_id: UUID
) -> BankConnectionModel | None:
    result = await db.execute(
        select(BankConnectionModel).where(
            BankConnectionModel.user_id == user_id,
            BankConnectionModel.connection_id == connection_id,
        )
    )
    return result.scalar_one_or_none()


async def get_bank_by_id(db: AsyncSession, bank_id: UUID) -> BankModel | None:
    return await db.get(BankModel, bank_id)


async def get_or_create_bank(db: AsyncSession, name: str, country_code: str) -> BankModel:
    result = await db.execute(
        select(BankModel).where(BankModel.name == name, BankModel.country_code == country_code)
    )
    bank = result.scalar_one_or_none()
    if bank is None:
        bank = BankModel(name=name, country_code=country_code)
        db.add(bank)
        await db.commit()
        await db.refresh(bank)
    return bank

async def revoke_connection(db: AsyncSession, connection: BankConnectionModel) -> None:
    connection.status = "revoked"
    await db.commit()


async def supersede_active_connections_for_bank(
    db: AsyncSession, user_id: str, bank_id: UUID, except_connection_id: UUID
) -> None:
    # Scoped to one bank so reconnecting a bank replaces only that bank's
    # old connection — connections to other banks stay active (multi-bank).
    result = await db.execute(
        select(BankConnectionModel).where(
            BankConnectionModel.user_id == user_id,
            BankConnectionModel.bank_id == bank_id,
            BankConnectionModel.status == "active",
            BankConnectionModel.connection_id != except_connection_id,
        )
    )
    for connection in result.scalars().all():
        connection.status = "superseded"
    await db.commit()