from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vialbum API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    database_url: str | None = None
    jwt_secret: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    storage_provider: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "eu-central-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_bucket_name: str | None = None
    media_max_upload_bytes: int = 15 * 1024 * 1024
    media_signed_url_expire_seconds: int = 900
    geoapify_api_key: SecretStr | None = None
    geoapify_timeout_seconds: float = Field(default=3.0, gt=0, le=10)
    place_search_result_limit: int = Field(default=6, ge=1, le=10)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.app_env.casefold() != "production":
            return self
        missing = [
            name
            for name, value in {
                "DATABASE_URL": self.database_url,
                "JWT_SECRET": self.jwt_secret,
                "STORAGE_PROVIDER": self.storage_provider,
                "S3_ENDPOINT_URL": self.s3_endpoint_url,
                "S3_ACCESS_KEY_ID": self.s3_access_key_id,
                "S3_SECRET_ACCESS_KEY": self.s3_secret_access_key,
                "S3_BUCKET_NAME": self.s3_bucket_name,
                "GEOAPIFY_API_KEY": self.geoapify_api_key,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required production configuration: {', '.join(missing)}")
        if self.debug:
            raise ValueError("DEBUG must be false in production")
        return self

    @property
    def sqlalchemy_database_url(self) -> str | None:
        if self.database_url and self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
