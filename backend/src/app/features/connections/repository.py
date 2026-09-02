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
