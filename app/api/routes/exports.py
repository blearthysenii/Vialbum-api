import uuid
from pathlib import Path

from fastapi import APIRouter, Query
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.services.exports import ExportService

router = APIRouter(tags=["exports"])


def _response(path: Path, filename: str) -> FileResponse:
    return FileResponse(
        path,
        filename=filename,
        media_type="application/zip",
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


@router.get("/journeys/{journey_id}/export", response_class=FileResponse)
def export_journey(
    journey_id: uuid.UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    include_media: bool = Query(default=True),
) -> FileResponse:
    path, filename = ExportService(session, storage).journey_export(
        current_user, journey_id, include_media
    )
    return _response(path, filename)


@router.get("/account/export", response_class=FileResponse)
def export_account(
    current_user: CurrentUser, session: DatabaseSession, storage: MediaStorage
) -> FileResponse:
    path, filename = ExportService(session, storage).account_export(current_user)
    return _response(path, filename)
