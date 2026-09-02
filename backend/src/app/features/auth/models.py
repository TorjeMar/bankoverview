from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)