from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.schemas.system import ApiInfo, HealthStatus
from app.services.health import database_is_available

router = APIRouter(tags=["system"])


@router.get("/", response_model=ApiInfo)
def api_info() -> ApiInfo:
    settings = get_settings()
    return ApiInfo(
        name=settings.app_name, version=settings.app_version, environment=settings.app_env
    )


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus | JSONResponse:
    if not database_is_available():
        payload = HealthStatus(status="unhealthy", database="unavailable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload.model_dump()
        )
    return HealthStatus(status="healthy", database="connected")
