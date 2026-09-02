import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.media import Media
from app.models.memory import Memory
from app.models.place import Place
from app.models.refresh_session import RefreshSession
from app.models.user import User
from tests.conftest import FakeObjectStorage, test_engine
from tests.helpers import auth_headers, journey_payload, login_user, register_user
from tests.test_media import JPEG, PLACE_SELECTION

PASSWORD = "a-strong-test-password"


def setup_account(client: TestClient, email: str = "delete@example.com"):
    user = register_user(client, email=email, password=PASSWORD)
    token = login_user(client, email=email, password=PASSWORD)
    headers = auth_headers(token)
    payload = journey_payload("Owned journey")
    payload["place"] = PLACE_SELECTION
    journey = client.post("/journeys", json=payload, headers=headers).json()
    memory = client.post(
        f"/journeys/{journey['id']}/memories",
        json={"title": "Owned memory", "memory_date": "2025-03-14", "place": PLACE_SELECTION},
        headers=headers,
    ).json()
    media = client.post(
        f"/journeys/{journey['id']}/media",
        files={"file": ("owned.jpg", JPEG, "image/jpeg")},
        headers=headers,
    ).json()
    with Session(test_engine) as session:
        session.add(
            RefreshSession(
                user_id=uuid.UUID(user["id"]),
                token_hash=hashlib.sha256(f"refresh:{email}".encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.commit()
        place_id = session.scalar(
            select(Journey.place_id).where(Journey.id == uuid.UUID(journey["id"]))
        )
    return token, headers, user, journey, memory, media, place_id


def delete(client: TestClient, headers: dict[str, str], password: str = PASSWORD):
    return client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": password},
    )


def test_account_deletion_requires_authentication_and_confirmation(client: TestClient) -> None:
    assert (
        client.request(
            "DELETE", "/auth/account", json={"confirmation": "DELETE", "password": PASSWORD}
        ).status_code
        == 401
    )
    _token, headers, *_ = setup_account(client)
    assert (
        client.request(
            "DELETE",
            "/auth/account",
            headers=headers,
            json={"confirmation": "delete", "password": PASSWORD},
        ).status_code
        == 422
    )
    assert delete(client, headers, "wrong-password").status_code == 401


def test_deletion_removes_owned_rows_sessions_and_invalidates_token(client: TestClient) -> None:
    token, headers, user, journey, memory, media, place_id = setup_account(client)
    assert delete(client, headers).status_code == 204
    with Session(test_engine) as session:
        assert session.get(User, uuid.UUID(user["id"])) is None
        assert session.get(Journey, uuid.UUID(journey["id"])) is None
        assert session.get(Memory, uuid.UUID(memory["id"])) is None
        assert session.get(Media, uuid.UUID(media["id"])) is None
        assert session.scalar(select(func.count()).select_from(RefreshSession)) == 0
        assert session.get(Place, place_id) is not None
    assert client.get("/auth/me", headers=auth_headers(token)).status_code == 401
    assert delete(client, headers).status_code == 401


def test_deletion_cleans_only_owned_storage_and_preserves_other_user(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    _token, owner, _user, _journey, _memory, owned_media, _place = setup_account(client)
    _other_token, other, other_user, other_journey, _other_memory, other_media, _ = setup_account(
        client, "other-delete@example.com"
    )
    fake_storage.deleted_keys.clear()
    assert delete(client, owner).status_code == 204
    assert any(owned_media["id"] in key for key in fake_storage.deleted_keys)
    assert not any(other_media["id"] in key for key in fake_storage.deleted_keys)
    assert client.get("/auth/me", headers=other).status_code == 200
    with Session(test_engine) as session:
        assert session.get(User, uuid.UUID(other_user["id"])) is not None
        assert session.get(Journey, uuid.UUID(other_journey["id"])) is not None


def test_storage_failure_preserves_account_and_marks_retry(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    _token, headers, user, journey, memory, media, _place = setup_account(client)
    fake_storage.fail_delete = True
    response = delete(client, headers)
    assert response.status_code == 503
    assert "remains active" in response.json()["detail"]
    with Session(test_engine) as session:
        assert session.get(User, uuid.UUID(user["id"])) is not None
        assert session.get(Journey, uuid.UUID(journey["id"])) is not None
        assert session.get(Memory, uuid.UUID(memory["id"])) is not None
        stored_media = session.get(Media, uuid.UUID(media["id"]))
        assert stored_media is not None and stored_media.deletion_pending_at is not None

    fake_storage.fail_delete = False
    assert delete(client, headers).status_code == 204
