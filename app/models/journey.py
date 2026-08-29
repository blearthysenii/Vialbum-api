import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.media import Media
    from app.models.memory import Memory
    from app.models.user import User


class Journey(TimestampMixin, Base):
    __tablename__ = "journeys"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_journeys_date_order"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    destination: Mapped[str] = mapped_column(String(160), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "media.id",
            ondelete="SET NULL",
            name="fk_journeys_cover_media_id_media",
            use_alter=True,
        ),
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="journeys")
    memories: Mapped[list["Memory"]] = relationship(
        back_populates="journey", cascade="all, delete-orphan", passive_deletes=True
    )
    media: Mapped[list["Media"]] = relationship(
        back_populates="journey",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Media.journey_id",
    )
    cover_media: Mapped["Media | None"] = relationship(
        foreign_keys=[cover_media_id], post_update=True
    )
