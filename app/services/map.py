from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError
from app.models.journey import Journey
from app.models.media import Media
from app.models.memory import Memory
from app.models.user import User
from app.repositories.journeys import JourneyRepository
from app.repositories.map import MapRepository
from app.repositories.media import MediaRepository
from app.schemas.map import MapItem
from app.storage.service import StorageOperationError, StorageService


class MapService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.journeys = JourneyRepository(session)
        self.map_items = MapRepository(session)
        self.media = MediaRepository(session)
        self.storage = storage

    def list(self, user: User) -> list[MapItem]:
        journeys = self.journeys.list_for_user(user.id)
        journey_ids = [journey.id for journey in journeys]
        memories = self.map_items.list_memories(journey_ids)
        photos = self.map_items.list_photos(journey_ids)
        journey_by_id = {journey.id: journey for journey in journeys}
        child_points: dict[object, list[tuple[Decimal, Decimal]]] = defaultdict(list)
        for item in [*memories, *photos]:
            if item.latitude is not None and item.longitude is not None:
                child_points[item.journey_id].append((item.latitude, item.longitude))

        items: list[MapItem] = []
        for journey in journeys:
            center = self._journey_center(journey, child_points[journey.id])
            if center:
                items.append(self._journey_item(journey, *center))
        items.extend(
            self._memory_item(memory, journey_by_id[memory.journey_id]) for memory in memories
        )
        items.extend(self._photo_item(photo, journey_by_id[photo.journey_id]) for photo in photos)
        return items

    @staticmethod
    def _journey_center(
        journey: Journey, child_points: list[tuple[Decimal, Decimal]]
    ) -> tuple[Decimal, Decimal] | None:
        if journey.latitude is not None and journey.longitude is not None:
            return journey.latitude, journey.longitude
        if not child_points:
            return None
        count = Decimal(len(child_points))
        precision = Decimal("0.000001")
        return (
            (sum(point[0] for point in child_points) / count).quantize(precision),
            (sum(point[1] for point in child_points) / count).quantize(precision),
        )

    def _read_url(self, key: str | None) -> str | None:
        if not key:
            return None
        try:
            return self.storage.create_read_url(key=key)
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc

    def _journey_item(self, journey: Journey, latitude: Decimal, longitude: Decimal) -> MapItem:
        cover = (
            self.media.get_for_journey(journey.cover_media_id, journey.id)
            if journey.cover_media_id
            else None
        )
        return MapItem(
            type="journey",
            id=journey.id,
            journey_id=journey.id,
            latitude=latitude,
            longitude=longitude,
            title=journey.title,
            subtitle=f"{journey.destination}, {journey.country}",
            date=journey.start_date,
            thumbnail_url=self._read_url(cover.storage_key if cover else None),
        )

    @staticmethod
    def _memory_item(memory: Memory, journey: Journey) -> MapItem:
        assert memory.latitude is not None and memory.longitude is not None
        return MapItem(
            type="memory",
            id=memory.id,
            journey_id=memory.journey_id,
            latitude=memory.latitude,
            longitude=memory.longitude,
            title=memory.title,
            subtitle=journey.title,
            date=memory.memory_date,
            caption=memory.caption,
        )

    def _photo_item(self, photo: Media, journey: Journey) -> MapItem:
        assert photo.latitude is not None and photo.longitude is not None
        key = photo.thumbnail_storage_key or photo.display_storage_key or photo.storage_key
        return MapItem(
            type="photo",
            id=photo.id,
            journey_id=photo.journey_id,
            latitude=photo.latitude,
            longitude=photo.longitude,
            title=photo.original_filename or "Photo",
            subtitle=journey.title,
            date=(photo.captured_at or photo.created_at).date(),
            thumbnail_url=self._read_url(key),
            caption=photo.caption,
        )
