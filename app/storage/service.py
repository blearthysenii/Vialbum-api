from functools import lru_cache
from typing import BinaryIO

from app.core.config import Settings, get_settings
from app.storage.base import ObjectStorage
from app.storage.s3 import S3ObjectStorage


class StorageConfigurationError(RuntimeError):
    pass


class StorageOperationError(RuntimeError):
    pass


class StorageService:
    def __init__(self, backend: ObjectStorage, *, read_url_expires_in: int) -> None:
        self.backend = backend
        self.read_url_expires_in = read_url_expires_in

    def upload(self, *, key: str, body: BinaryIO, content_type: str, content_length: int) -> None:
        try:
            self.backend.upload(
                key=key, body=body, content_type=content_type, content_length=content_length
            )
        except Exception as exc:
            raise StorageOperationError("Photo storage is temporarily unavailable") from exc

    def delete(self, *, key: str) -> None:
        try:
            self.backend.delete(key=key)
        except Exception as exc:
            raise StorageOperationError("Photo storage is temporarily unavailable") from exc

    def download_to(self, *, key: str, destination: BinaryIO) -> None:
        try:
            self.backend.download_to(key=key, destination=destination)
        except Exception as exc:
            raise StorageOperationError("Photo storage is temporarily unavailable") from exc

    def create_read_url(self, *, key: str) -> str:
        try:
            return self.backend.create_read_url(key=key, expires_in=self.read_url_expires_in)
        except Exception as exc:
            raise StorageOperationError("Photo storage is temporarily unavailable") from exc


def _require(value: str | None, name: str) -> str:
    if not value:
        raise StorageConfigurationError(f"{name} is required for media storage")
    return value


def build_storage_service(settings: Settings) -> StorageService:
    if settings.storage_provider != "supabase_s3":
        raise StorageConfigurationError("Unsupported or missing storage provider")
    access_key = settings.s3_access_key_id
    secret_key = settings.s3_secret_access_key
    if access_key is None or secret_key is None:
        raise StorageConfigurationError("S3 credentials are required for media storage")
    backend = S3ObjectStorage(
        endpoint_url=_require(settings.s3_endpoint_url, "S3_ENDPOINT_URL"),
        region=settings.s3_region,
        access_key_id=access_key.get_secret_value(),
        secret_access_key=secret_key.get_secret_value(),
        bucket=_require(settings.s3_bucket_name, "S3_BUCKET_NAME"),
    )
    return StorageService(backend, read_url_expires_in=settings.media_signed_url_expire_seconds)


@lru_cache
def get_storage_service() -> StorageService:
    return build_storage_service(get_settings())
