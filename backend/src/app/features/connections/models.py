from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BankConnectionModel(Base):
    __tablename__ = "bank_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    enable_banking_session_id: Mapped[str]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aspsp: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    account_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
