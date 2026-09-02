import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.models.journey import Journey
from app.models.media import Media, MediaType
from app.models.memory import Memory
from app.models.place import Place


class SearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def journeys(self, user_id: uuid.UUID, pattern: str) -> list[Journey]:
        statement = (
            select(Journey)
            .outerjoin(Place, Place.id == Journey.place_id)
            .options(selectinload(Journey.place), selectinload(Journey.cover_media))
            .where(
                Journey.user_id == user_id,
                or_(
                    Journey.title.ilike(pattern, escape="\\"),
                    Journey.destination.ilike(pattern, escape="\\"),
                    Journey.country.ilike(pattern, escape="\\"),
                    Journey.description.ilike(pattern, escape="\\"),
                    Place.name.ilike(pattern, escape="\\"),
                    Place.display_name.ilike(pattern, escape="\\"),
                    Place.locality.ilike(pattern, escape="\\"),
                    Place.region.ilike(pattern, escape="\\"),
                    Place.country.ilike(pattern, escape="\\"),
                ),
            )
        )
        return list(self.session.scalars(statement).unique())

    def memories(self, user_id: uuid.UUID, pattern: str) -> list[Memory]:
        statement = (
            select(Memory)
            .join(Journey, Journey.id == Memory.journey_id)
            .outerjoin(Place, Place.id == Memory.place_id)
            .options(selectinload(Memory.place), selectinload(Memory.journey))
            .where(
                Journey.user_id == user_id,
                or_(
                    Memory.title.ilike(pattern, escape="\\"),
                    Memory.caption.ilike(pattern, escape="\\"),
                    Place.name.ilike(pattern, escape="\\"),
                    Place.display_name.ilike(pattern, escape="\\"),
                    Place.locality.ilike(pattern, escape="\\"),
                    Place.region.ilike(pattern, escape="\\"),
                    Place.country.ilike(pattern, escape="\\"),
                ),
            )
        )
        return list(self.session.scalars(statement).unique())

    def photos(self, user_id: uuid.UUID, pattern: str) -> list[Media]:
        place = aliased(Place)
        memory = aliased(Memory)
        statement = (
            select(Media)
            .join(Journey, Journey.id == Media.journey_id)
            .outerjoin(place, place.id == Media.place_id)
            .outerjoin(memory, memory.id == Media.memory_id)
            .options(
                selectinload(Media.place),
                selectinload(Media.memory),
                selectinload(Media.journey),
            )
            .where(
                Journey.user_id == user_id,
                Media.type == MediaType.photo,
                or_(
                    Media.caption.ilike(pattern, escape="\\"),
                    place.name.ilike(pattern, escape="\\"),
                    place.display_name.ilike(pattern, escape="\\"),
                    place.locality.ilike(pattern, escape="\\"),
                    place.region.ilike(pattern, escape="\\"),
                    place.country.ilike(pattern, escape="\\"),
                    memory.title.ilike(pattern, escape="\\"),
                    memory.caption.ilike(pattern, escape="\\"),
                ),
            )
        )
        return list(self.session.scalars(statement).unique())
