import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, HttpUrl

from app.models.media import MediaType
from app.schemas.common import IdentifiedSchema, OrmSchema
from app.schemas.place import PlaceRead, PlaceSelection


class MediaBase(OrmSchema):
    type: MediaType
    original_filename: str | None = None
    mime_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    captured_at: datetime | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    sort_order: int = Field(default=0, ge=0)
    caption: str | None = None


class MediaRead(MediaBase, IdentifiedSchema):
    journey_id: uuid.UUID
    memory_id: uuid.UUID | None
    place_id: uuid.UUID | None
    place: PlaceRead | None = None
    url: HttpUrl
    thumbnail_url: HttpUrl | None = None


class MediaUpdate(OrmSchema):
    model_config = ConfigDict(extra="forbid")

    caption: str | None = None
    captured_at: datetime | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    place: PlaceSelection | None = None
    memory_id: uuid.UUID | None = None
