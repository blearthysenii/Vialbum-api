import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IdentifiedSchema(OrmSchema):
    id: uuid.UUID
    created_at: datetime
