import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedJourney(Base):
    __tablename__ = "saved_journeys"
    __table_args__ = (
        UniqueConstraint("user_id", "journey_id", name="uq_saved_journeys_user_journey"),
        Index("ix_saved_journeys_page", "user_id", "created_at", "id"),
        Index("ix_saved_journeys_journey_id", "journey_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    journey_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
