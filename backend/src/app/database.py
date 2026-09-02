from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.features.connections.schemas import PendingAuthorization


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


app_sessions: dict[str, dict[str, str]] = {}
pending_authorizations: dict[str, PendingAuthorization] = {}
