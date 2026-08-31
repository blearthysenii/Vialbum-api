import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common import IdentifiedSchema, OrmSchema


class MemoryBase(OrmSchema):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    caption: str | None = None
    memory_date: date
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)


class MemoryCreate(MemoryBase):
    journey_id: uuid.UUID


class MemoryRead(MemoryBase, IdentifiedSchema):
    journey_id: uuid.UUID
    updated_at: datetime


class MemoryUpdate(OrmSchema):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    caption: str | None = None
    memory_date: date | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        return MemoryBase.strip_title(value) if value is not None else None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "MemoryUpdate":
        for field in ("title", "memory_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
