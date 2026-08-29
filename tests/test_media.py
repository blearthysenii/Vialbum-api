from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.repositories.media import MediaRepository
from tests.conftest import FakeObjectStorage
from tests.helpers import auth_headers, journey_payload, login_user, register_user

JPEG = b"\xff\xd8\xff\xe0" + b"vialbum-photo"


def setup_owner(client: TestClient, *, email: str = "owner@example.com") -> tuple[dict, dict]:
    register_user(client, email=email)
    headers = auth_headers(login_user(client, email=email))
    journey_response = client.post("/journeys", json=journey_payload(), headers=headers)
    assert journey_response.status_code == 201
    return headers, journey_response.json()


def upload_photo(client: TestClient, journey_id: str, headers: dict[str, str]):
    return client.post(
        f"/journeys/{journey_id}/media",
        headers=headers,
        files={"file": ("medina.jpg", JPEG, "image/jpeg")},
        data={"width": "1200", "height": "900", "captured_at": "2025-03-14T10:00:00Z"},
    )


def test_unauthenticated_upload_rejected(client: TestClient) -> None:
    response = client.post(
        "/journeys/00000000-0000-0000-0000-000000000000/media",
        files={"file": ("photo.jpg", JPEG, "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_and_list_own_journey_media(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    headers, journey = setup_owner(client)
    response = upload_photo(client, journey["id"], headers)
    assert response.status_code == 201
    media = response.json()
    assert media["mime_type"] == "image/jpeg"
    assert media["width"] == 1200
    assert "storage_key" not in media
    assert len(fake_storage.objects) == 1

    listed = client.get(f"/journeys/{journey['id']}/media", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [media["id"]]


def test_another_user_cannot_upload_or_list(client: TestClient) -> None:
    owner_headers, journey = setup_owner(client)
    assert upload_photo(client, journey["id"], owner_headers).status_code == 201
    register_user(client, email="other@example.com")
    other = auth_headers(login_user(client, email="other@example.com"))
    assert upload_photo(client, journey["id"], other).status_code == 404
    assert client.get(f"/journeys/{journey['id']}/media", headers=other).status_code == 404


def test_missing_journey_upload_rejected(client: TestClient) -> None:
    register_user(client)
    headers = auth_headers(login_user(client))
    response = upload_photo(client, "00000000-0000-0000-0000-000000000000", headers)
    assert response.status_code == 404


def test_invalid_mime_content_rejected(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    response = client.post(
        f"/journeys/{journey['id']}/media",
        headers=headers,
        files={"file": ("malware.jpg", b"not-an-image", "image/jpeg")},
    )
    assert response.status_code == 422


def test_oversized_photo_rejected(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    oversized = JPEG + b"x" * 15728640
    response = client.post(
        f"/journeys/{journey['id']}/media",
        headers=headers,
        files={"file": ("large.jpg", oversized, "image/jpeg")},
    )
    assert response.status_code == 422


def test_delete_own_media(client: TestClient, fake_storage: FakeObjectStorage) -> None:
    headers, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], headers).json()
    response = client.delete(f"/journeys/{journey['id']}/media/{media['id']}", headers=headers)
    assert response.status_code == 204
    assert not fake_storage.objects
    assert client.get(f"/journeys/{journey['id']}/media", headers=headers).json() == []


def test_cannot_delete_another_users_media(client: TestClient) -> None:
    owner, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], owner).json()
    register_user(client, email="intruder@example.com")
    intruder = auth_headers(login_user(client, email="intruder@example.com"))
    response = client.delete(f"/journeys/{journey['id']}/media/{media['id']}", headers=intruder)
    assert response.status_code == 404


def test_cover_selection_and_delete_clears_cover(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], headers).json()
    covered = client.patch(f"/journeys/{journey['id']}/cover/{media['id']}", headers=headers)
    assert covered.status_code == 200
    assert covered.json()["cover_media_id"] == media["id"]
    assert covered.json()["cover_media_url"].startswith("https://private-storage.test/")

    deleted = client.delete(f"/journeys/{journey['id']}/media/{media['id']}", headers=headers)
    assert deleted.status_code == 204
    refreshed = client.get(f"/journeys/{journey['id']}", headers=headers).json()
    assert refreshed["cover_media_id"] is None
    assert refreshed["cover_media_url"] is None


def test_cannot_use_another_journeys_media_as_cover(client: TestClient) -> None:
    headers, first = setup_owner(client)
    second = client.post("/journeys", json=journey_payload("Milan"), headers=headers).json()
    media = upload_photo(client, first["id"], headers).json()
    response = client.patch(f"/journeys/{second['id']}/cover/{media['id']}", headers=headers)
    assert response.status_code == 404


def test_storage_upload_failure_leaves_no_metadata(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    headers, journey = setup_owner(client)
    fake_storage.fail_upload = True
    assert upload_photo(client, journey["id"], headers).status_code == 503
    fake_storage.fail_upload = False
    assert client.get(f"/journeys/{journey['id']}/media", headers=headers).json() == []


def test_database_failure_removes_uploaded_object(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    headers, journey = setup_owner(client)
    with patch.object(MediaRepository, "create", side_effect=RuntimeError("database failure")):
        with pytest.raises(RuntimeError, match="database failure"):
            upload_photo(client, journey["id"], headers)
    assert not fake_storage.objects


def test_storage_delete_failure_preserves_metadata(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    headers, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], headers).json()
    fake_storage.fail_delete = True
    response = client.delete(f"/journeys/{journey['id']}/media/{media['id']}", headers=headers)
    assert response.status_code == 503
    fake_storage.fail_delete = False
    assert len(client.get(f"/journeys/{journey['id']}/media", headers=headers).json()) == 1
