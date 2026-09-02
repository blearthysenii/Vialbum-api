from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError, InvalidInputError
from app.models.journey import Journey
from app.models.media import Media
from app.models.memory import Memory
from app.models.user import User
from app.repositories.search import SearchRepository
from app.schemas.search import (
    JourneySearchResult,
    MemorySearchResult,
    PhotoSearchResult,
    SearchResponse,
)
from app.storage.service import StorageOperationError, StorageService

RESULT_LIMIT = 10


def _text(value: object | None) -> str:
    return str(value).strip().casefold() if value is not None else ""


def _field_score(value: object | None, query: str, primary: bool) -> int:
    value = _text(value)
    if not value:
        return 0
    if value == query:
        match = 1000 if primary else 500
    elif value.startswith(query):
        match = 900 if primary else 400
    elif re.search(rf"(?:^|\W){re.escape(query)}(?:$|\W)", value):
        match = 800 if primary else 300
    elif query in value:
        match = 700 if primary else 200
    else:
        return 0
    return match


def _best(query: str, primary: Iterable[object | None], secondary: Iterable[object | None]) -> int:
    return max(
        [
            *(_field_score(value, query, True) for value in primary),
            *(_field_score(value, query, False) for value in secondary),
        ],
        default=0,
    )


def _place_fields(item: Journey | Memory | Media) -> list[str | None]:
    place = item.place
    if place is None:
        return []
    return [place.name, place.display_name, place.locality, place.region, place.country]


class SearchService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.search = SearchRepository(session)
        self.storage = storage

    def run(self, user: User, query: str) -> SearchResponse:
        normalized = query.strip()
        if len(normalized) < 2:
            raise InvalidInputError("Search requires at least 2 characters")
        if len(normalized) > 100:
            raise InvalidInputError("Search cannot exceed 100 characters")
        folded = normalized.casefold()
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        journeys = self.search.journeys(user.id, pattern)
        memories = self.search.memories(user.id, pattern)
        photos = self.search.photos(user.id, pattern)

        journeys.sort(
            key=lambda item: (
                -self._journey_score(item, folded),
                item.title.casefold(),
                str(item.id),
            )
        )
        memories.sort(
            key=lambda item: (-self._memory_score(item, folded), item.memory_date, str(item.id))
        )
        photos.sort(
            key=lambda item: (
                -self._photo_score(item, folded),
                item.captured_at or item.created_at,
                str(item.id),
            )
        )

        return SearchResponse(
            query=normalized,
            journeys=[self._journey_result(item) for item in journeys[:RESULT_LIMIT]],
            memories=[self._memory_result(item) for item in memories[:RESULT_LIMIT]],
            photos=[self._photo_result(item) for item in photos[:RESULT_LIMIT]],
        )

    @staticmethod
    def _journey_score(item: Journey, query: str) -> int:
        return _best(
            query,
            [item.title],
            [item.destination, item.country, item.description, *_place_fields(item)],
        )

    @staticmethod
    def _memory_score(item: Memory, query: str) -> int:
        return _best(query, [item.title], [item.caption, *_place_fields(item)])

    @staticmethod
    def _photo_score(item: Media, query: str) -> int:
        return _best(
            query,
            [item.caption],
            [
                *_place_fields(item),
                item.memory.title if item.memory else None,
                item.memory.caption if item.memory else None,
            ],
        )

    def _thumbnail(self, media: Media | None) -> str | None:
        if media is None:
            return None
        key = media.thumbnail_storage_key or media.display_storage_key or media.storage_key
        try:
            return self.storage.create_read_url(key=key)
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc

    def _journey_result(self, item: Journey) -> JourneySearchResult:
        return JourneySearchResult(
            id=item.id,
            title=item.title,
            destination=item.destination,
            country=item.country,
            start_date=item.start_date,
            end_date=item.end_date,
            location=item.place.display_name if item.place else None,
            thumbnail_url=self._thumbnail(item.cover_media),
        )

    @staticmethod
    def _memory_result(item: Memory) -> MemorySearchResult:
        return MemorySearchResult(
            id=item.id,
            journey_id=item.journey_id,
            journey_title=item.journey.title,
            journey_start_date=item.journey.start_date,
            title=item.title,
            date=item.memory_date,
            location=item.place.display_name if item.place else None,
            context=item.caption,
        )

    def _photo_result(self, item: Media) -> PhotoSearchResult:
        return PhotoSearchResult(
            id=item.id,
            journey_id=item.journey_id,
            journey_title=item.journey.title,
            date=(item.captured_at or item.created_at).date(),
            caption=item.caption,
            location=item.place.display_name if item.place else None,
            memory_title=item.memory.title if item.memory else None,
            thumbnail_url=self._thumbnail(item),
        )
