import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_configuration_fails_fast_when_critical_values_are_missing() -> None:
    with pytest.raises(ValidationError, match="Missing required production configuration"):
        Settings(app_env="production", _env_file=None)


def test_production_configuration_requires_debug_off() -> None:
    values = {
        "app_env": "production",
        "database_url": "postgresql://example",
        "jwt_secret": "secret",
        "storage_provider": "supabase_s3",
        "s3_endpoint_url": "https://storage.example.com",
        "s3_access_key_id": "access",
        "s3_secret_access_key": "secret",
        "s3_bucket_name": "private",
        "geoapify_api_key": "geo",
    }
    with pytest.raises(ValidationError, match="DEBUG must be false"):
        Settings(**values, debug=True, _env_file=None)
    assert Settings(**values, debug=False, _env_file=None).app_env == "production"
