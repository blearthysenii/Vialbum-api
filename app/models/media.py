import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.journey import Journey
    from app.models.memory import Memory
    from app.models.place import Place


class MediaType(StrEnum):
    photo = "photo"
    video = "video"


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_media_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_media_longitude"),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_media_coordinate_pair"
        ),
        CheckConstraint("sort_order >= 0", name="ck_media_sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journey_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("journeys.id", ondelete="CASCADE"), index=True, nullable=False
    )
    memory_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("memories.id", ondelete="SET NULL"), index=True
    )
    place_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("places.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="media_type", native_enum=True), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(Text)
    display_storage_key: Mapped[str | None] = mapped_column(Text)
    deletion_pending_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    caption: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    journey: Mapped["Journey"] = relationship(back_populates="media", foreign_keys=[journey_id])
    memory: Mapped["Memory | None"] = relationship(back_populates="media")
    place: Mapped["Place | None"] = relationship(back_populates="media")
