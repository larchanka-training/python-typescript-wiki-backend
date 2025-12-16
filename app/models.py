from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tmp(Base):
    __tablename__ = "tmp"

    id: Mapped[int] = mapped_column(primary_key=True)

