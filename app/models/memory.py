import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.journey import Journey
    from app.models.media import Media
    from app.models.place import Place


class Memory(TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_memories_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_memories_longitude"),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_memories_coordinate_pair",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journey_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("journeys.id", ondelete="CASCADE"), index=True, nullable=False
    )
    place_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("places.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    memory_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    journey: Mapped["Journey"] = relationship(back_populates="memories")
    place: Mapped["Place | None"] = relationship(back_populates="memories")
    media: Mapped[list["Media"]] = relationship(back_populates="memory", passive_deletes=True)
