import uuid
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.saved_journey import SavedJourney
from app.repositories.discover import DiscoverRepository


class SocialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def public_count(self, owner_id: uuid.UUID) -> int:
        return (
            self.session.scalar(
                select(func.count(Journey.id)).where(
                    Journey.user_id == owner_id, Journey.visibility == "public"
                )
            )
            or 0
        )

    def saved_ids(self, viewer_id: uuid.UUID, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        return set(
            self.session.scalars(
                select(SavedJourney.journey_id).where(
                    SavedJourney.user_id == viewer_id, SavedJourney.journey_id.in_(ids)
                )
            )
        )

    def save(self, viewer_id: uuid.UUID, journey_id: uuid.UUID) -> None:
        # The unique constraint handles concurrent duplicate POSTs as well.
        try:
            with self.session.begin_nested():
                self.session.add(SavedJourney(user_id=viewer_id, journey_id=journey_id))
                self.session.flush()
        except IntegrityError:
            if journey_id not in self.saved_ids(viewer_id, [journey_id]):
                raise
        self.session.commit()

    def remove(self, viewer_id: uuid.UUID, journey_id: uuid.UUID) -> None:
        self.session.execute(
            delete(SavedJourney).where(
                SavedJourney.user_id == viewer_id, SavedJourney.journey_id == journey_id
            )
        )
        self.session.commit()

    def page(self, viewer_id: uuid.UUID, limit: int, after: tuple[datetime, uuid.UUID] | None):
        query = (
            DiscoverRepository._query()
            .add_columns(SavedJourney)
            .join(SavedJourney, SavedJourney.journey_id == Journey.id)
            .where(
                SavedJourney.user_id == viewer_id,
                Journey.visibility == "public",
                Journey.user_id != viewer_id,
            )
        )
        if after:
            created_at, identifier = after
            query = query.where(
                or_(
                    SavedJourney.created_at < created_at,
                    and_(SavedJourney.created_at == created_at, SavedJourney.id < identifier),
                )
            )
        return list(
            self.session.execute(
                query.order_by(SavedJourney.created_at.desc(), SavedJourney.id.desc()).limit(
                    limit + 1
                )
            )
        )
