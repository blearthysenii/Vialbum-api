from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError, NotFoundError
from app.models.journey import Journey
from app.models.media import Media
from app.models.memory import Memory
from app.models.user import User
from app.repositories.journeys import JourneyRepository
from app.repositories.map import MapRepository
from app.schemas.map import MapItem, MapThumbnail
from app.storage.service import StorageOperationError, StorageService


class MapService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.journeys = JourneyRepository(session)
        self.map_items = MapRepository(session)
        self.storage = storage

    def list(self, user: User, *, include_thumbnails: bool = True) -> list[MapItem]:
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
                items.append(
                    self._journey_item(journey, *center, include_thumbnail=include_thumbnails)
                )
        items.extend(
            self._memory_item(memory, journey_by_id[memory.journey_id]) for memory in memories
        )
        items.extend(
            self._photo_item(
                photo,
                journey_by_id[photo.journey_id],
                include_thumbnail=include_thumbnails,
            )
            for photo in photos
        )
        return items

    def thumbnail(self, user: User, item_type: str, item_id: uuid.UUID) -> MapThumbnail:
        key: str | None = None
        if item_type == "journey":
            journey = self.journeys.get_for_user(item_id, user.id)
            if journey is None:
                raise NotFoundError("Map item not found")
            key = self._thumbnail_key(journey.cover_media)
        elif item_type == "photo":
            photo = self.map_items.get_photo_for_user(item_id, user.id)
            if photo is None:
                raise NotFoundError("Map item not found")
            key = self._thumbnail_key(photo)
        elif item_type == "memory":
            if self.map_items.get_memory_for_user(item_id, user.id) is None:
                raise NotFoundError("Map item not found")
        else:
            raise NotFoundError("Map item not found")
        return MapThumbnail(thumbnail_url=self._read_url(key))

    @staticmethod
    def _thumbnail_key(media: Media | None) -> str | None:
        if media is None:
            return None
        return media.thumbnail_storage_key or media.display_storage_key or media.storage_key

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

    def _journey_item(
        self,
        journey: Journey,
        latitude: Decimal,
        longitude: Decimal,
        *,
        include_thumbnail: bool,
    ) -> MapItem:
        cover = journey.cover_media
        return MapItem(
            type="journey",
            id=journey.id,
            journey_id=journey.id,
            latitude=latitude,
            longitude=longitude,
            title=journey.title,
            subtitle=f"{journey.destination}, {journey.country}",
            date=journey.start_date,
            thumbnail_url=(
                self._read_url(self._thumbnail_key(cover)) if include_thumbnail else None
            ),
            thumbnail_revision=str(cover.id) if cover else None,
            location=journey.place.display_name if journey.place else None,
            journey_start_date=journey.start_date,
            journey_end_date=journey.end_date,
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
            location=memory.place.display_name if memory.place else None,
            journey_start_date=journey.start_date,
            journey_end_date=journey.end_date,
        )

    def _photo_item(self, photo: Media, journey: Journey, *, include_thumbnail: bool) -> MapItem:
        assert photo.latitude is not None and photo.longitude is not None
        key = self._thumbnail_key(photo)
        return MapItem(
            type="photo",
            id=photo.id,
            journey_id=photo.journey_id,
            latitude=photo.latitude,
            longitude=photo.longitude,
            title=photo.original_filename or "Photo",
            subtitle=journey.title,
            date=(photo.captured_at or photo.created_at).date(),
            thumbnail_url=self._read_url(key) if include_thumbnail else None,
            thumbnail_revision=str(photo.id),
            caption=photo.caption,
            location=photo.place.display_name if photo.place else None,
            journey_start_date=journey.start_date,
            journey_end_date=journey.end_date,
            memory_id=photo.memory_id,
            memory_title=photo.memory.title if photo.memory else None,
        )
