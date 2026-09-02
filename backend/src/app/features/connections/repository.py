from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.connections.models import BankConnectionModel


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
