from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidInputError, NotFoundError
from app.models.journey import Journey
from app.models.media import Media
from app.models.memory import Memory
from app.models.place import Place
from app.models.user import User
from app.repositories.journeys import JourneyRepository
from app.repositories.media import MediaRepository
from app.repositories.memories import MemoryRepository
from app.storage.service import StorageOperationError, StorageService

EXPORT_VERSION = 1
MAX_MEDIA_FILES = 5000
MAX_DECLARED_MEDIA_BYTES = 2 * 1024 * 1024 * 1024


def _iso(value: object | None) -> str | None:
    return (
        value.isoformat()
        if hasattr(value, "isoformat")
        else str(value)
        if value is not None
        else None
    )


def _place(place: Place | None) -> dict[str, Any] | None:
    if place is None:
        return None
    return {
        "id": str(place.id),
        "provider": place.provider,
        "provider_place_id": place.provider_place_id,
        "display_name": place.display_name,
        "name": place.name,
        "locality": place.locality,
        "region": place.region,
        "country": place.country,
        "country_code": place.country_code,
        "latitude": str(place.latitude),
        "longitude": str(place.longitude),
    }


def _journey(item: Journey) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "destination": item.destination,
        "country": item.country,
        "start_date": _iso(item.start_date),
        "end_date": _iso(item.end_date),
        "description": item.description,
        "latitude": _iso(item.latitude),
        "longitude": _iso(item.longitude),
        "place": _place(item.place),
        "cover_media_id": _iso(item.cover_media_id),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _memory(item: Memory) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "journey_id": str(item.journey_id),
        "title": item.title,
        "caption": item.caption,
        "memory_date": _iso(item.memory_date),
        "latitude": _iso(item.latitude),
        "longitude": _iso(item.longitude),
        "place": _place(item.place),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _media(item: Media) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "journey_id": str(item.journey_id),
        "memory_id": _iso(item.memory_id),
        "type": item.type.value,
        "original_filename": item.original_filename,
        "mime_type": item.mime_type,
        "file_size": item.file_size,
        "width": item.width,
        "height": item.height,
        "caption": item.caption,
        "captured_at": _iso(item.captured_at),
        "latitude": _iso(item.latitude),
        "longitude": _iso(item.longitude),
        "place": _place(item.place),
        "sort_order": item.sort_order,
        "created_at": _iso(item.created_at),
    }


def _safe_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w -]", "", value, flags=re.UNICODE).strip().replace(" ", "-")
    return cleaned[:80] or fallback


def _media_filename(item: Media, used: set[str]) -> str:
    original = PurePath((item.original_filename or "").replace("\\", "/")).name
    suffix = Path(original).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }.get(item.mime_type, ".bin")
    stem = _safe_component(Path(original).stem, f"photo-{item.id}")
    candidate = f"{stem}{suffix}"
    number = 2
    while candidate.casefold() in used:
        candidate = f"{stem}-{number}{suffix}"
        number += 1
    used.add(candidate.casefold())
    return candidate


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


class ExportService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.journeys = JourneyRepository(session)
        self.memories = MemoryRepository(session)
        self.media = MediaRepository(session)
        self.storage = storage

    def journey_export(
        self, user: User, journey_id: uuid.UUID, include_media: bool
    ) -> tuple[Path, str]:
        journey = self.journeys.get_for_user(journey_id, user.id)
        if journey is None:
            raise NotFoundError("Journey not found")
        memories = self.memories.list_for_journey(journey.id)
        media = self.media.list_for_journey(journey.id)
        if include_media:
            self._validate_size(media)
        root = f"Vialbum-{_safe_component(journey.title, 'Journey')}-{journey.start_date.year}"
        path = self._temporary_path()
        try:
            with zipfile.ZipFile(
                path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as archive:
                records = (
                    self._write_media(archive, root, media)
                    if include_media
                    else [
                        {
                            **_media(item),
                            "exported_file": None,
                            "exported_variant": None,
                            "export_error": None,
                        }
                        for item in media
                    ]
                )
                archive.writestr(
                    f"{root}/journey.json",
                    _json({"export_version": EXPORT_VERSION, **_journey(journey)}),
                )
                archive.writestr(
                    f"{root}/memories.json",
                    _json(
                        {
                            "export_version": EXPORT_VERSION,
                            "memories": [_memory(item) for item in memories],
                        }
                    ),
                )
                archive.writestr(
                    f"{root}/media.json",
                    _json({"export_version": EXPORT_VERSION, "media": records}),
                )
                archive.writestr(
                    f"{root}/README.txt",
                    self._readme(journey, len(memories), len(media), include_media),
                )
            return path, f"{root}.zip"
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def account_export(self, user: User) -> tuple[Path, str]:
        journeys = self.journeys.list_for_user(user.id)
        memories = [
            item for journey in journeys for item in self.memories.list_for_journey(journey.id)
        ]
        media = [item for journey in journeys for item in self.media.list_for_journey(journey.id)]
        places = {
            item.place.id: item.place for item in [*journeys, *memories, *media] if item.place
        }
        path = self._temporary_path()
        root = "Vialbum-Account-Export"
        try:
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    f"{root}/account.json",
                    _json(
                        {
                            "export_version": EXPORT_VERSION,
                            "account": {
                                "id": str(user.id),
                                "email": user.email,
                                "first_name": user.first_name,
                                "last_name": user.last_name,
                                "created_at": _iso(user.created_at),
                                "updated_at": _iso(user.updated_at),
                            },
                        }
                    ),
                )
                archive.writestr(
                    f"{root}/journeys.json",
                    _json(
                        {
                            "export_version": EXPORT_VERSION,
                            "journeys": [_journey(item) for item in journeys],
                        }
                    ),
                )
                archive.writestr(
                    f"{root}/memories.json",
                    _json(
                        {
                            "export_version": EXPORT_VERSION,
                            "memories": [_memory(item) for item in memories],
                        }
                    ),
                )
                archive.writestr(
                    f"{root}/media.json",
                    _json(
                        {
                            "export_version": EXPORT_VERSION,
                            "media": [_media(item) for item in media],
                        }
                    ),
                )
                archive.writestr(
                    f"{root}/places.json",
                    _json(
                        {
                            "export_version": EXPORT_VERSION,
                            "places": [_place(item) for item in places.values()],
                        }
                    ),
                )
                archive.writestr(
                    f"{root}/README.txt",
                    "\n".join(
                        [
                            "Vialbum account data export",
                            f"Created: {datetime.now(UTC).isoformat()}",
                            f"Export version: {EXPORT_VERSION}",
                            f"Journeys: {len(journeys)}",
                            f"Memories: {len(memories)}",
                            f"Media records: {len(media)}",
                            "Original media files are not included in account exports.",
                            "",
                        ]
                    ),
                )
            return path, "Vialbum-Account-Export.zip"
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _temporary_path() -> Path:
        descriptor, name = tempfile.mkstemp(prefix="vialbum-export-", suffix=".zip")
        os.close(descriptor)
        return Path(name)

    @staticmethod
    def _validate_size(media: list[Media]) -> None:
        if len(media) > MAX_MEDIA_FILES:
            raise InvalidInputError("This journey has too many media files for a direct export")
        if sum(item.file_size for item in media) > MAX_DECLARED_MEDIA_BYTES:
            raise InvalidInputError("This journey export is too large to prepare directly")

    def _write_media(
        self, archive: zipfile.ZipFile, root: str, media: list[Media]
    ) -> list[dict[str, Any]]:
        used: set[str] = set()
        records: list[dict[str, Any]] = []
        for item in media:
            filename = _media_filename(item, used)
            exported_file = None
            exported_variant = None
            for variant, key in (
                ("original", item.storage_key),
                ("display", item.display_storage_key),
                ("thumbnail", item.thumbnail_storage_key),
            ):
                if not key:
                    continue
                try:
                    with tempfile.TemporaryFile() as downloaded:
                        self.storage.download_to(key=key, destination=downloaded)
                        downloaded.seek(0)
                        with archive.open(f"{root}/photos/{filename}", "w") as destination:
                            shutil.copyfileobj(downloaded, destination, length=1024 * 1024)
                    exported_file = f"photos/{filename}"
                    exported_variant = variant
                    break
                except StorageOperationError:
                    continue
            records.append(
                {
                    **_media(item),
                    "exported_file": exported_file,
                    "exported_variant": exported_variant,
                    "export_error": None
                    if exported_file
                    else "Media file was unavailable during export",
                }
            )
        return records

    @staticmethod
    def _readme(journey: Journey, memories: int, media: int, included: bool) -> str:
        return "\n".join(
            [
                "Vialbum journey export",
                f"Created: {datetime.now(UTC).isoformat()}",
                f"Journey: {journey.title}",
                f"Export version: {EXPORT_VERSION}",
                f"Memories: {memories}",
                f"Media records: {media}",
                f"Original media requested: {'yes' if included else 'no'}",
                "JSON files use stable, portable field names and ISO dates.",
                "",
            ]
        )
