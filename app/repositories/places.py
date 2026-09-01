from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.place import Place
from app.schemas.place import PlaceSelection


class PlaceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_provider_identity(self, provider: str, provider_place_id: str) -> Place | None:
        return self.session.scalar(
            select(Place).where(
                Place.provider == provider, Place.provider_place_id == provider_place_id
            )
        )

    def get_or_create(self, selection: PlaceSelection) -> Place:
        existing = self.get_by_provider_identity(selection.provider, selection.provider_place_id)
        if existing is not None:
            return existing
        place = Place(**selection.model_dump(mode="python"))
        try:
            with self.session.begin_nested():
                self.session.add(place)
                self.session.flush()
        except IntegrityError:
            existing = self.get_by_provider_identity(
                selection.provider, selection.provider_place_id
            )
            if existing is None:
                raise
            return existing
        return place
