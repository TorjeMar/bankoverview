from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import SessionModel, UserModel


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


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> UserModel | None:
    result = await db.execute(select(UserModel).where(UserModel.user_id == user_id))
    return result.scalar_one_or_none()


async def create_session(
    db: AsyncSession, user_id: UUID, expires_at: datetime, created_at: datetime
) -> SessionModel:
    session = SessionModel(user_id=user_id, expires_at=expires_at, created_at=created_at)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: UUID) -> SessionModel | None:
    result = await db.execute(
        select(SessionModel).where(SessionModel.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, session_id: UUID) -> None:
    session = await get_session(db, session_id)
    if session is not None:
        await db.delete(session)
        await db.commit()
