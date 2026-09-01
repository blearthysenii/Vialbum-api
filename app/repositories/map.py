import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.journey import Journey
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
            .options(selectinload(Memory.place))
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
            .options(selectinload(Media.place), selectinload(Media.memory))
            .where(
                Media.journey_id.in_(journey_ids),
                Media.type == MediaType.photo,
                Media.latitude.is_not(None),
                Media.longitude.is_not(None),
            )
            .order_by(Media.captured_at.asc().nulls_last(), Media.created_at.asc(), Media.id.asc())
        )
        return list(self.session.scalars(statement))

    def get_photo_for_user(self, media_id: uuid.UUID, user_id: uuid.UUID) -> Media | None:
        statement = (
            select(Media)
            .join(Journey, Journey.id == Media.journey_id)
            .where(
                Media.id == media_id,
                Media.type == MediaType.photo,
                Journey.user_id == user_id,
            )
        )
        return self.session.scalar(statement)

    def get_memory_for_user(self, memory_id: uuid.UUID, user_id: uuid.UUID) -> Memory | None:
        statement = (
            select(Memory)
            .join(Journey, Journey.id == Memory.journey_id)
            .where(Memory.id == memory_id, Journey.user_id == user_id)
        )
        return self.session.scalar(statement)
