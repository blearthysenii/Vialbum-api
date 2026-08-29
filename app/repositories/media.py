import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

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
            .where(Media.journey_id == journey_id)
            .order_by(Media.sort_order.asc(), Media.created_at.asc(), Media.id.asc())
        )
        return list(self.session.scalars(statement))

    def get_for_journey(self, media_id: uuid.UUID, journey_id: uuid.UUID) -> Media | None:
        statement = select(Media).where(Media.id == media_id, Media.journey_id == journey_id)
        return self.session.scalar(statement)

    def delete(self, media: Media, journey: Journey) -> None:
        if journey.cover_media_id == media.id:
            journey.cover_media_id = None
        self.session.delete(media)
        self.session.commit()
