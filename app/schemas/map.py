import uuid
from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class MapItem(BaseModel):
    type: Literal["journey", "memory", "photo"]
    id: uuid.UUID
    journey_id: uuid.UUID
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)
    title: str
    subtitle: str | None = None
    date: Date | None = None
    thumbnail_url: HttpUrl | None = None
    caption: str | None = None
