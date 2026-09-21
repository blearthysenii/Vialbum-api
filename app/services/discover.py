import base64
import binascii
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError, InvalidInputError, NotFoundError
from app.models.journey import Journey
from app.models.media import MediaType
from app.models.saved_journey import SavedJourney
from app.models.user import User
from app.models.user_follow import UserFollow
from app.repositories.discover import DiscoverRepository
from app.repositories.media import MediaRepository
from app.repositories.memories import MemoryRepository
from app.repositories.social import SocialRepository
from app.schemas.discover import (
    DiscoverJourney,
    DiscoverPage,
    PublicCreator,
    PublicJourneyDetail,
    PublicPhoto,
)
from app.schemas.journey import JourneyRead
from app.schemas.memory import MemoryRead
from app.storage.service import StorageOperationError, StorageService


def encode_cursor(journey: Journey | SavedJourney | UserFollow) -> str:
    created_at = journey.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{journey.id}".encode()).decode()


def decode_cursor(value: str | None) -> tuple[datetime, uuid.UUID] | None:
    if value is None:
        return None
    try:
        timestamp, identifier = (
            base64.b64decode(value, altchars=b"-_", validate=True).decode().split("|")
        )
        created_at = datetime.fromisoformat(timestamp)
        if created_at.tzinfo is None:
            raise ValueError("missing timezone")
        return created_at.astimezone(UTC), uuid.UUID(identifier)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise InvalidInputError("Invalid discovery cursor") from exc


class DiscoverService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.repository = DiscoverRepository(session)
        self.media = MediaRepository(session)
        self.memories = MemoryRepository(session)
        self.storage = storage
        self.social = SocialRepository(session)

    def _url(self, key: str | None) -> str | None:
        if not key:
            return None
        try:
            return self.storage.create_read_url(key=key)
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc

    def _card(self, journey: Journey, photo_count: int, memory_count: int) -> DiscoverJourney:
        cover = journey.cover_media
        if cover is not None and (
            cover.journey_id != journey.id
            or cover.deletion_pending_at is not None
            or cover.type != MediaType.photo
        ):
            cover = None
        creator = journey.user
        return DiscoverJourney(
            **JourneyRead.model_validate(journey).model_dump(exclude={"cover_media_url"}),
            cover_media_url=self._url(
                (cover.display_storage_key or cover.storage_key) if cover else None
            ),
            cover_width=cover.width if cover else None,
            cover_height=cover.height if cover else None,
            creator=PublicCreator(
                id=creator.id,
                username=creator.username,
                display_name=" ".join(filter(None, [creator.first_name, creator.last_name]))
                or creator.username,
                avatar_url=self._url(creator.profile_photo_storage_key),
            ),
            photo_count=photo_count,
            memory_count=memory_count,
        )

    def cards(self, user: User, journeys: list[Journey]) -> list[DiscoverJourney]:
        ids = [journey.id for journey in journeys]
        photos, memories = self.repository.counts(ids)
        saved = self.social.saved_ids(user.id, ids)
        cards = []
        for journey in journeys:
            card = self._card(journey, photos.get(journey.id, 0), memories.get(journey.id, 0))
            card.is_saved = journey.id in saved
            cards.append(card)
        return cards

    def page(
        self,
        user: User,
        *,
        limit: int,
        cursor: str | None,
        owner_id: uuid.UUID | None = None,
        following_only: bool = False,
    ) -> DiscoverPage:
        journeys = self.repository.page(
            user.id, limit, decode_cursor(cursor), owner_id, following_only
        )
        page = journeys[:limit]
        return DiscoverPage(
            items=self.cards(user, page),
            next_cursor=encode_cursor(page[-1]) if len(journeys) > limit else None,
        )

    def detail(self, user: User, journey_id: uuid.UUID) -> PublicJourneyDetail:
        # Authorization must happen before loading or signing any child media.
        journey = self.repository.viewable(journey_id, user.id)
        if journey is None:
            raise NotFoundError("Journey not found")
        photos = [
            photo
            for photo in self.media.list_for_journey(journey.id)
            if photo.type == MediaType.photo and photo.deletion_pending_at is None
        ]
        memories = self.memories.list_for_journey(journey.id)
        card = self._card(journey, len(photos), len(memories))
        card.is_saved = journey.id in self.social.saved_ids(user.id, [journey.id])
        return PublicJourneyDetail(
            **card.model_dump(),
            memories=[MemoryRead.model_validate(memory) for memory in memories],
            photos=[
                PublicPhoto(
                    id=photo.id,
                    memory_id=photo.memory_id,
                    caption=photo.caption,
                    url=self._url(photo.display_storage_key or photo.storage_key),
                    thumbnail_url=self._url(photo.thumbnail_storage_key),
                    width=photo.width,
                    height=photo.height,
                    captured_at=photo.captured_at,
                    created_at=photo.created_at,
                    latitude=photo.latitude,
                    longitude=photo.longitude,
                    place=photo.place,
                )
                for photo in photos
            ],
        )
