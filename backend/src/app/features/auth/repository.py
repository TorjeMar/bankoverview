from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import UserModel


async def get_or_create_user(db: AsyncSession, user_id: UUID) -> UserModel:
    result = await db.execute(select(UserModel).where(UserModel.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = UserModel(user_id=user_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
