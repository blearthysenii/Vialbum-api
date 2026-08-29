import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.journey import Journey
    from app.models.memory import Memory


class MediaType(StrEnum):
    photo = "photo"
    video = "video"


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_media_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_media_longitude"),
        CheckConstraint("sort_order >= 0", name="ck_media_sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journey_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("journeys.id", ondelete="CASCADE"), index=True, nullable=False
    )
    memory_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("memories.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="media_type", native_enum=True), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    journey: Mapped["Journey"] = relationship(back_populates="media")
    memory: Mapped["Memory | None"] = relationship(back_populates="media")
