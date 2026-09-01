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


def test_caption_is_returned_and_can_be_added_edited_and_cleared(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], headers).json()
    assert media["caption"] is None
    url = f"/journeys/{journey['id']}/media/{media['id']}"

    added = client.patch(url, json={"caption": "Sunset over the water"}, headers=headers)
    assert added.status_code == 200
    assert added.json()["caption"] == "Sunset over the water"
    listed = client.get(f"/journeys/{journey['id']}/media", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["caption"] == "Sunset over the water"

    edited = client.patch(url, json={"caption": "Our last evening"}, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["caption"] == "Our last evening"

    cleared = client.patch(url, json={"caption": None}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["caption"] is None
    assert (
        client.get(f"/journeys/{journey['id']}/media", headers=headers).json()[0]["caption"] is None
    )


def test_caption_update_requires_authentication(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], headers).json()
    url = f"/journeys/{journey['id']}/media/{media['id']}"
    assert client.patch(url, json={"caption": "Not allowed"}).status_code == 401
    listed = client.get(f"/journeys/{journey['id']}/media", headers=headers).json()
    assert listed[0]["caption"] is None


def test_caption_update_is_journey_and_owner_scoped(client: TestClient) -> None:
    owner, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], owner).json()
    url = f"/journeys/{journey['id']}/media/{media['id']}"

    register_user(client, email="caption-intruder@example.com")
    intruder = auth_headers(login_user(client, email="caption-intruder@example.com"))
    assert client.patch(url, json={"caption": "Stolen"}, headers=intruder).status_code == 404

    other_journey = client.post("/journeys", json=journey_payload("Other"), headers=owner).json()
    wrong_url = f"/journeys/{other_journey['id']}/media/{media['id']}"
    assert client.patch(wrong_url, json={"caption": "Moved"}, headers=owner).status_code == 404
    assert (
        client.get(f"/journeys/{journey['id']}/media", headers=owner).json()[0]["caption"] is None
    )


def test_media_update_rejects_unrelated_fields(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    media = upload_photo(client, journey["id"], headers).json()
    url = f"/journeys/{journey['id']}/media/{media['id']}"
    response = client.patch(url, json={"storage_key": "unsafe"}, headers=headers)
    assert response.status_code == 422


PLACE_SELECTION = {
    "provider": "geoapify",
    "provider_place_id": "photo-medina",
    "display_name": "Medina, Saudi Arabia",
    "name": "Medina",
    "locality": "Medina",
    "region": "Al Madinah",
    "country": "Saudi Arabia",
    "country_code": "SA",
    "latitude": "24.468600",
    "longitude": "39.614200",
}


def test_photo_location_date_and_memory_updates(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    photo = upload_photo(client, journey["id"], headers).json()
    memory_url = f"/journeys/{journey['id']}/memories"
    first = client.post(
        memory_url, json={"title": "First", "memory_date": "2025-03-14"}, headers=headers
    ).json()
    second = client.post(
        memory_url, json={"title": "Second", "memory_date": "2025-03-15"}, headers=headers
    ).json()
    url = f"/journeys/{journey['id']}/media/{photo['id']}"

    assigned = client.patch(
        url,
        json={
            "place": PLACE_SELECTION,
            "latitude": "24.500000",
            "longitude": "39.700000",
            "captured_at": "2025-03-18T15:30:00Z",
            "memory_id": first["id"],
        },
        headers=headers,
    )
    assert assigned.status_code == 200
    body = assigned.json()
    assert body["place_id"] == body["place"]["id"]
    assert body["latitude"] == "24.500000"
    assert body["place"]["latitude"] == "24.468600"
    assert body["captured_at"].startswith("2025-03-18T15:30:00")
    assert body["memory_id"] == first["id"]

    changed = client.patch(url, json={"memory_id": second["id"]}, headers=headers)
    assert changed.status_code == 200 and changed.json()["memory_id"] == second["id"]
    removed = client.patch(url, json={"memory_id": None}, headers=headers)
    assert removed.status_code == 200 and removed.json()["memory_id"] is None
    cleared = client.patch(url, json={"place": None}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["place_id"] is None
    assert cleared.json()["latitude"] is None


def test_photo_custom_coordinates_and_exif_correction(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    photo = upload_photo(client, journey["id"], headers).json()
    url = f"/journeys/{journey['id']}/media/{photo['id']}"
    custom = client.patch(
        url, json={"latitude": "10.000000", "longitude": "20.000000"}, headers=headers
    )
    assert custom.status_code == 200
    corrected = client.patch(
        url, json={"latitude": "11.000000", "longitude": "21.000000"}, headers=headers
    )
    assert corrected.status_code == 200
    assert corrected.json()["latitude"] == "11.000000"


@pytest.mark.parametrize(
    "body", [{"latitude": 91, "longitude": 20}, {"latitude": 20}, {"longitude": 20}]
)
def test_photo_rejects_invalid_or_incomplete_coordinates(client: TestClient, body: dict) -> None:
    headers, journey = setup_owner(client)
    photo = upload_photo(client, journey["id"], headers).json()
    url = f"/journeys/{journey['id']}/media/{photo['id']}"
    assert client.patch(url, json=body, headers=headers).status_code == 422


def test_photo_rejects_memory_from_another_journey_and_user(client: TestClient) -> None:
    headers, journey = setup_owner(client)
    photo = upload_photo(client, journey["id"], headers).json()
    other_journey = client.post("/journeys", json=journey_payload("Other"), headers=headers).json()
    memory = client.post(
        f"/journeys/{other_journey['id']}/memories",
        json={"title": "Elsewhere", "memory_date": "2025-03-14"},
        headers=headers,
    ).json()
    url = f"/journeys/{journey['id']}/media/{photo['id']}"
    assert client.patch(url, json={"memory_id": memory["id"]}, headers=headers).status_code == 422
