import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field, HttpUrl

from app.models.media import MediaType
from app.schemas.common import IdentifiedSchema, OrmSchema


class MediaBase(OrmSchema):
    type: MediaType
    url: HttpUrl
    thumbnail_url: HttpUrl | None = None
    captured_at: datetime | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    sort_order: int = Field(default=0, ge=0)


class MediaCreate(MediaBase):
    journey_id: uuid.UUID
    memory_id: uuid.UUID | None = None


class MediaRead(MediaBase, IdentifiedSchema):
    journey_id: uuid.UUID
    memory_id: uuid.UUID | None
