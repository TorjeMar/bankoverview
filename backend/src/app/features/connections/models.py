from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BankModel(Base):
    __tablename__ = "banks"

    bank_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str]
    country_code: Mapped[str]

class BankConnectionModel(Base):
    __tablename__ = "bank_connections"

    connection_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id"))
    bank_id: Mapped[UUID] = mapped_column(ForeignKey("banks.bank_id"))
    enable_banking_session_id: Mapped[str]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


