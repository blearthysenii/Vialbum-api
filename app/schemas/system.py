from pydantic import BaseModel


class ApiInfo(BaseModel):
    name: str
    version: str
    environment: str


class HealthStatus(BaseModel):
    status: str
    database: str
