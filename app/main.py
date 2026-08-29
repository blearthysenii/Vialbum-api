from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    ConfigurationError,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    UnauthorizedError,
)

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)
app.include_router(api_router)


@app.exception_handler(ConflictError)
def conflict_error_handler(_request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.detail})


@app.exception_handler(ConfigurationError)
def configuration_error_handler(_request: Request, exc: ConfigurationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": exc.detail}
    )


@app.exception_handler(UnauthorizedError)
def unauthorized_error_handler(_request: Request, exc: UnauthorizedError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": exc.detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(NotFoundError)
def not_found_error_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.detail})


@app.exception_handler(InvalidInputError)
def invalid_input_error_handler(_request: Request, exc: InvalidInputError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": exc.detail}
    )
