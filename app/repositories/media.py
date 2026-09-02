import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.journey import Journey
from app.models.media import Media


class MediaRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, values: dict[str, Any]) -> Media:
        media = Media(**values)
        self.session.add(media)
        self.session.commit()
        self.session.refresh(media)
        return media

    def list_for_journey(self, journey_id: uuid.UUID) -> list[Media]:
        statement = (
            select(Media)
            .options(selectinload(Media.place))
            .where(Media.journey_id == journey_id)
            .order_by(Media.sort_order.asc(), Media.created_at.asc(), Media.id.asc())
        )
        return list(self.session.scalars(statement))

    def list_for_user(self, user_id: uuid.UUID) -> list[Media]:
        statement = (
            select(Media)
            .join(Journey, Journey.id == Media.journey_id)
            .where(Journey.user_id == user_id)
            .order_by(Media.created_at.asc(), Media.id.asc())
        )
        return list(self.session.scalars(statement))

    def mark_deletion_pending(self, media: list[Media], timestamp: datetime) -> None:
        for item in media:
            item.deletion_pending_at = timestamp
        self.session.commit()

    def get_for_journey(self, media_id: uuid.UUID, journey_id: uuid.UUID) -> Media | None:
        statement = (
            select(Media)
            .options(selectinload(Media.place))
            .where(Media.id == media_id, Media.journey_id == journey_id)
        )
        return self.session.scalar(statement)

    def update(self, media: Media, values: dict[str, Any]) -> Media:
        for field, value in values.items():
            setattr(media, field, value)
        self.session.commit()
        self.session.refresh(media)
        return media

    def delete(self, media: Media, journey: Journey) -> None:
        if journey.cover_media_id == media.id:
            journey.cover_media_id = None
        self.session.delete(media)
        self.session.commit()
