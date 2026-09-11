import uuid
from io import BytesIO

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError, ConflictError, InvalidInputError
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.user import UserRead, UserUpdate
from app.services.media import _detect_image
from app.storage.service import StorageOperationError, StorageService


class UserService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self.session = session
        self.storage = storage
        self.users = UserRepository(session)

    def serialize(self, user: User) -> UserRead:
        photo_url = None
        cover_url = None
        if user.profile_photo_storage_key:
            try:
                photo_url = self.storage.create_read_url(key=user.profile_photo_storage_key)
            except StorageOperationError as exc:
                raise ConfigurationError(str(exc)) from exc
        if user.profile_cover_storage_key:
            try:
                cover_url = self.storage.create_read_url(key=user.profile_cover_storage_key)
            except StorageOperationError as exc:
                raise ConfigurationError(str(exc)) from exc
        return UserRead.model_validate({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "bio": user.bio,
            "location": user.location,
            "profile_photo_url": photo_url,
            "profile_cover_url": cover_url,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        })

    def update(self, user: User, payload: UserUpdate) -> User:
        username = payload.username.strip().casefold()
        owner = self.users.get_by_username(username)
        if owner is not None and owner.id != user.id:
            raise ConflictError("This username is already taken.", code="USERNAME_TAKEN")
        try:
            return self.users.update(user, {
                "first_name": payload.first_name.strip(),
                "last_name": payload.last_name.strip(),
                "username": username,
                "bio": payload.bio,
                "location": payload.location,
            })
        except IntegrityError:
            raise ConflictError("This username is already taken.", code="USERNAME_TAKEN") from None

    def upload_photo(self, user: User, body: bytes) -> User:
        maximum = get_settings().media_max_upload_bytes
        if not body:
            raise InvalidInputError("The selected photo is empty")
        if len(body) > maximum:
            raise InvalidInputError(f"Photo exceeds the {maximum // (1024 * 1024)} MB limit")
        mime_type, extension = _detect_image(body)
        key = f"users/{user.id}/profile/{uuid.uuid4()}.{extension}"
        previous_key = user.profile_photo_storage_key
        try:
            self.storage.upload(
                key=key,
                body=BytesIO(body),
                content_type=mime_type,
                content_length=len(body),
            )
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc
        try:
            updated = self.users.update(user, {"profile_photo_storage_key": key})
        except Exception:
            try:
                self.storage.delete(key=key)
            except StorageOperationError:
                pass
            raise
        if previous_key:
            try:
                self.storage.delete(key=previous_key)
            except StorageOperationError:
                pass
        return updated

    def remove_photo(self, user: User) -> User:
        previous_key = user.profile_photo_storage_key
        updated = self.users.update(user, {"profile_photo_storage_key": None})
        if previous_key:
            try:
                self.storage.delete(key=previous_key)
            except StorageOperationError:
                pass
        return updated

    def upload_cover(self, user: User, body: bytes) -> User:
        return self._replace_image(user, body, kind="cover", field="profile_cover_storage_key")

    def remove_cover(self, user: User) -> User:
        previous_key = user.profile_cover_storage_key
        updated = self.users.update(user, {"profile_cover_storage_key": None})
        if previous_key:
            try:
                self.storage.delete(key=previous_key)
            except StorageOperationError:
                pass
        return updated

    def _replace_image(self, user: User, body: bytes, *, kind: str, field: str) -> User:
        maximum = get_settings().media_max_upload_bytes
        if not body:
            raise InvalidInputError("The selected photo is empty")
        if len(body) > maximum:
            raise InvalidInputError(f"Photo exceeds the {maximum // (1024 * 1024)} MB limit")
        mime_type, extension = _detect_image(body)
        key = f"users/{user.id}/profile/{kind}/{uuid.uuid4()}.{extension}"
        previous_key = getattr(user, field)
        try:
            self.storage.upload(
                key=key,
                body=BytesIO(body),
                content_type=mime_type,
                content_length=len(body),
            )
        except StorageOperationError as exc:
            raise ConfigurationError(str(exc)) from exc
        try:
            updated = self.users.update(user, {field: key})
        except Exception:
            try:
                self.storage.delete(key=key)
            except StorageOperationError:
                pass
            raise
        if previous_key:
            try:
                self.storage.delete(key=previous_key)
            except StorageOperationError:
                pass
        return updated
