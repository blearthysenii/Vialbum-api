import re
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import PurePath

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError, InvalidInputError, NotFoundError
from app.models.journey import Journey
from app.models.media import Media, MediaType
from app.models.user import User
from app.repositories.journeys import JourneyRepository
from app.repositories.media import MediaRepository
from app.schemas.journey import JourneyRead
from app.schemas.media import MediaRead
from app.storage.service import StorageOperationError, StorageService

_IMAGE_SIGNATURES = {
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/heic": (
        "heic",
        lambda data: (
            len(data) >= 12
            and data[4:8] == b"ftyp"
            and data[8:12] in {b"heic", b"heix", b"hevc", b"hevx"}
        ),
    ),
    "image/heif": (
        "heif",
        lambda data: len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"mif1", b"msf1"},
    ),
}


def _detect_image(data: bytes) -> tuple[str, str]:
    for mime_type, (extension, matcher) in _IMAGE_SIGNATURES.items():
        if matcher(data):
            return mime_type, extension
    raise InvalidInputError("Only valid JPEG, PNG, HEIC, or HEIF photos are supported")


def _safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    name = PurePath(filename.replace("\\", "/")).name
    name = re.sub(r"[^\w.() -]", "_", name, flags=re.UNICODE).strip(" .")
    return name[:255] or None


class MediaService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.session = session
        self.storage = storage
        self.journeys = JourneyRepository(session)
        self.media = MediaRepository(session)

    def _journey(self, user: User, journey_id: uuid.UUID) -> Journey:
        journey = self.journeys.get_for_user(journey_id, user.id)
        if journey is None:
            raise NotFoundError("Journey not found")
        return journey

    def upload_photo(
        self,
        *,
        user: User,
        journey_id: uuid.UUID,
        filename: str | None,
        body: bytes,
        captured_at: datetime | None,
        width: int | None,
        height: int | None,
        latitude: Decimal | None,
        longitude: Decimal | None,
    ) -> Media:
        self._journey(user, journey_id)
        maximum = get_settings().media_max_upload_bytes
        if not body:
            raise InvalidInputError("The selected photo is empty")
        if len(body) > maximum:
            raise InvalidInputError(f"Photo exceeds the {maximum // (1024 * 1024)} MB limit")
        mime_type, extension = _detect_image(body)
        media_id = uuid.uuid4()
        key = f"users/{user.id}/journeys/{journey_id}/{media_id}.{extension}"
        try:
            self.storage.upload(
                key=key,
                body=BytesIO(body),
                content_type=mime_type,
                content_length=len(body),
            )
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc
        try:
            return self.media.create(
                values={
                    "id": media_id,
                    "journey_id": journey_id,
                    "type": MediaType.photo,
                    "storage_key": key,
                    "original_filename": _safe_filename(filename),
                    "mime_type": mime_type,
                    "file_size": len(body),
                    "width": width,
                    "height": height,
                    "captured_at": captured_at,
                    "latitude": latitude,
                    "longitude": longitude,
                }
            )
        except Exception:
            self.session.rollback()
            try:
                self.storage.delete(key=key)
            except StorageOperationError:
                pass
            raise

    def list(self, user: User, journey_id: uuid.UUID) -> list[Media]:
        self._journey(user, journey_id)
        return self.media.list_for_journey(journey_id)

    def get(self, user: User, journey_id: uuid.UUID, media_id: uuid.UUID) -> Media:
        self._journey(user, journey_id)
        media = self.media.get_for_journey(media_id, journey_id)
        if media is None:
            raise NotFoundError("Photo not found")
        return media

    def delete(self, user: User, journey_id: uuid.UUID, media_id: uuid.UUID) -> None:
        journey = self._journey(user, journey_id)
        media = self.get(user, journey_id, media_id)
        try:
            self.storage.delete(key=media.storage_key)
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc
        self.media.delete(media, journey)

    def set_cover(self, user: User, journey_id: uuid.UUID, media_id: uuid.UUID) -> Journey:
        journey = self._journey(user, journey_id)
        self.get(user, journey_id, media_id)
        return self.journeys.update(journey, {"cover_media_id": media_id})

    def serialize(self, media: Media) -> MediaRead:
        try:
            url = self.storage.create_read_url(key=media.storage_key)
            thumbnail_url = (
                self.storage.create_read_url(key=media.thumbnail_storage_key)
                if media.thumbnail_storage_key
                else None
            )
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc
        return MediaRead(
            id=media.id,
            created_at=media.created_at,
            journey_id=media.journey_id,
            memory_id=media.memory_id,
            type=media.type,
            original_filename=media.original_filename,
            mime_type=media.mime_type,
            file_size=media.file_size,
            width=media.width,
            height=media.height,
            captured_at=media.captured_at,
            latitude=media.latitude,
            longitude=media.longitude,
            sort_order=media.sort_order,
            url=url,
            thumbnail_url=thumbnail_url,
        )

    def serialize_journey(self, journey: Journey) -> JourneyRead:
        cover_url = None
        if journey.cover_media_id:
            cover = self.media.get_for_journey(journey.cover_media_id, journey.id)
            if cover:
                try:
                    cover_url = self.storage.create_read_url(key=cover.storage_key)
                except StorageOperationError as exc:
                    raise ConfigurationError(str(exc)) from exc
        result = JourneyRead.model_validate(journey)
        return JourneyRead.model_validate({**result.model_dump(), "cover_media_url": cover_url})
