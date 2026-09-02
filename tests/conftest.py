import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["JWT_SECRET"] = "test-only-secret-not-used-outside-tests"

import app.models  # noqa: E402, F401
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.storage.service import StorageService, get_storage_service  # noqa: E402


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_upload = False
        self.fail_delete = False
        self.deleted_keys: list[str] = []

    def reset(self) -> None:
        self.objects.clear()
        self.fail_upload = False
        self.fail_delete = False
        self.deleted_keys.clear()

    def upload(self, *, key: str, body: object, content_type: str, content_length: int) -> None:
        if self.fail_upload:
            raise RuntimeError("simulated upload failure")
        self.objects[key] = body.read()  # type: ignore[attr-defined]

    def delete(self, *, key: str) -> None:
        if self.fail_delete:
            raise RuntimeError("simulated delete failure")
        self.deleted_keys.append(key)
        self.objects.pop(key, None)

    def download_to(self, *, key: str, destination: object) -> None:
        if key not in self.objects:
            raise FileNotFoundError(key)
        destination.write(self.objects[key])  # type: ignore[attr-defined]

    def create_read_url(self, *, key: str, expires_in: int) -> str:
        return f"https://private-storage.test/{key}?expires={expires_in}"


fake_object_storage = FakeObjectStorage()
fake_storage_service = StorageService(fake_object_storage, read_url_expires_in=900)

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def override_get_db() -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_storage_service] = lambda: fake_storage_service


@pytest.fixture(autouse=True)
def isolated_database() -> Generator[None, None, None]:
    get_settings.cache_clear()
    fake_object_storage.reset()
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_storage() -> FakeObjectStorage:
    return fake_object_storage
