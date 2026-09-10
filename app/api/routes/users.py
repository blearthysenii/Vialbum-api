from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.core.config import get_settings
from app.schemas.user import UserRead, UserUpdate
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> UserRead:
    service = UserService(session, storage)
    return service.serialize(service.update(current_user, payload))


@router.post("/me/profile-photo", response_model=UserRead)
async def upload_profile_photo(
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
    file: Annotated[UploadFile, File()],
) -> UserRead:
    body = await file.read(get_settings().media_max_upload_bytes + 1)
    service = UserService(session, storage)
    return service.serialize(service.upload_photo(current_user, body))


@router.delete("/me/profile-photo", status_code=status.HTTP_204_NO_CONTENT)
def remove_profile_photo(
    current_user: CurrentUser, session: DatabaseSession, storage: MediaStorage
) -> Response:
    UserService(session, storage).remove_photo(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
