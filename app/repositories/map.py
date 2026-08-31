import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media import Media, MediaType
from app.models.memory import Memory


class MapRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_memories(self, journey_ids: list[uuid.UUID]) -> list[Memory]:
        if not journey_ids:
            return []
        statement = (
            select(Memory)
            .where(
                Memory.journey_id.in_(journey_ids),
                Memory.latitude.is_not(None),
                Memory.longitude.is_not(None),
            )
            .order_by(Memory.memory_date.asc(), Memory.created_at.asc(), Memory.id.asc())
        )
        return list(self.session.scalars(statement))

    def list_photos(self, journey_ids: list[uuid.UUID]) -> list[Media]:
        if not journey_ids:
            return []
        statement = (
            select(Media)
            .where(
                Media.journey_id.in_(journey_ids),
                Media.type == MediaType.photo,
                Media.latitude.is_not(None),
                Media.longitude.is_not(None),
            )
            .order_by(Media.captured_at.asc().nulls_last(), Media.created_at.asc(), Media.id.asc())
        )
        return list(self.session.scalars(statement))
