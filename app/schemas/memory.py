import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import IdentifiedSchema, OrmSchema


class MemoryBase(OrmSchema):
    title: str = Field(min_length=1, max_length=160)
    caption: str | None = None
    memory_date: date
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)


class MemoryCreate(MemoryBase):
    journey_id: uuid.UUID


class MemoryRead(MemoryBase, IdentifiedSchema):
    journey_id: uuid.UUID
    updated_at: datetime
