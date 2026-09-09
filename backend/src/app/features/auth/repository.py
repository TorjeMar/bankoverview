from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import UserModel


async def get_or_create_user_by_google_subject(
    db: AsyncSession, subject: str, email: str
) -> UserModel:
    result = await db.execute(
        select(UserModel).where(UserModel.google_subject == subject)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = UserModel(google_subject=subject, email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif user.email != email:
        user.email = email
        await db.commit()

    return user
