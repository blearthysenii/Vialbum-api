from fastapi.testclient import TestClient

from tests.helpers import auth_headers, journey_payload, login_user, register_user
from tests.test_media import JPEG


def owner(client: TestClient, email: str = "mapper@example.com") -> tuple[dict[str, str], dict]:
    register_user(client, email=email)
    headers = auth_headers(login_user(client, email=email))
    journey = client.post(
        "/journeys",
        json={**journey_payload(), "latitude": "41.327500", "longitude": "19.818700"},
        headers=headers,
    ).json()
    return headers, journey


def memory(client: TestClient, headers: dict[str, str], journey_id: str, **values: str):
    return client.post(
        f"/journeys/{journey_id}/memories",
        json={
            "title": "Old Bazaar",
            "caption": "An afternoon walk",
            "memory_date": "2025-03-14",
            "latitude": "41.330000",
            "longitude": "19.820000",
            **values,
        },
        headers=headers,
    )


def photo(client: TestClient, headers: dict[str, str], journey_id: str, **values: str):
    return client.post(
        f"/journeys/{journey_id}/media",
        headers=headers,
        files={"file": ("square.jpg", JPEG, "image/jpeg")},
        data={
            "captured_at": "2025-03-15T10:00:00Z",
            "latitude": "41.340000",
            "longitude": "19.830000",
            **values,
        },
    )


def test_map_items_require_authentication(client: TestClient) -> None:
    assert client.get("/map/items").status_code == 401


def test_map_returns_owned_journey_memory_and_photo(client: TestClient) -> None:
    headers, journey = owner(client)
    created_memory = memory(client, headers, journey["id"]).json()
    created_photo = photo(client, headers, journey["id"]).json()
    response = client.get("/map/items", headers=headers)
    assert response.status_code == 200
    items = response.json()
    assert [item["type"] for item in items] == ["journey", "memory", "photo"]
    by_type = {item["type"]: item for item in items}
    assert by_type["journey"] == {
        "type": "journey",
        "id": journey["id"],
        "journey_id": journey["id"],
        "latitude": "41.327500",
        "longitude": "19.818700",
        "title": "Medina 2025",
        "subtitle": "Medina, Saudi Arabia",
        "date": "2025-03-12",
        "thumbnail_url": None,
        "thumbnail_revision": None,
        "caption": None,
        "location": None,
        "journey_start_date": "2025-03-12",
        "journey_end_date": "2025-03-19",
        "memory_id": None,
        "memory_title": None,
    }
    assert by_type["memory"]["id"] == created_memory["id"]
    assert by_type["memory"]["caption"] == "An afternoon walk"
    assert by_type["photo"]["id"] == created_photo["id"]
    assert by_type["photo"]["thumbnail_url"].startswith("https://private-storage.test/")
    assert by_type["photo"]["date"] == "2025-03-15"
    assert by_type["photo"]["journey_start_date"] == "2025-03-12"
    assert by_type["photo"]["journey_end_date"] == "2025-03-19"


def test_journey_uses_presentation_only_center_from_children(client: TestClient) -> None:
    headers, journey = owner(client)
    cleared = client.patch(
        f"/journeys/{journey['id']}",
        json={"latitude": None, "longitude": None},
        headers=headers,
    )
    assert cleared.status_code == 200
    memory(client, headers, journey["id"], latitude="40.000000", longitude="20.000000")
    photo(client, headers, journey["id"], latitude="42.000000", longitude="22.000000")
    items = client.get("/map/items", headers=headers).json()
    mapped_journey = next(item for item in items if item["type"] == "journey")
    assert mapped_journey["latitude"] == "41.000000"
    assert mapped_journey["longitude"] == "21.000000"
    stored = client.get(f"/journeys/{journey['id']}", headers=headers).json()
    assert stored["latitude"] is None
    assert stored["longitude"] is None


def test_map_excludes_unmapped_content(client: TestClient) -> None:
    register_user(client)
    headers = auth_headers(login_user(client))
    journey = client.post("/journeys", json=journey_payload(), headers=headers).json()
    memory(client, headers, journey["id"], latitude=None, longitude=None)
    response = client.get("/map/items", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_map_does_not_expose_other_users_items(client: TestClient) -> None:
    first, journey = owner(client, "first-map@example.com")
    memory(client, first, journey["id"])
    photo(client, first, journey["id"])
    second, second_journey = owner(client, "second-map@example.com")
    items = client.get("/map/items", headers=second).json()
    assert {item["journey_id"] for item in items} == {second_journey["id"]}


def test_journey_coordinates_must_be_complete_and_valid(client: TestClient) -> None:
    register_user(client)
    headers = auth_headers(login_user(client))
    assert (
        client.post(
            "/journeys", json={**journey_payload(), "latitude": 41}, headers=headers
        ).status_code
        == 422
    )


def test_map_can_skip_eager_thumbnail_signing(client: TestClient) -> None:
    headers, journey = owner(client)
    created_photo = photo(client, headers, journey["id"]).json()

    response = client.get("/map/items?include_thumbnails=false", headers=headers)

    assert response.status_code == 200
    assert all(item["thumbnail_url"] is None for item in response.json())
    thumbnail = client.get(f"/map/items/photo/{created_photo['id']}/thumbnail", headers=headers)
    assert thumbnail.status_code == 200
    assert thumbnail.json()["thumbnail_url"].startswith("https://private-storage.test/")


def test_map_thumbnail_is_ownership_protected(client: TestClient) -> None:
    first, journey = owner(client, "thumbnail-owner@example.com")
    created_photo = photo(client, first, journey["id"]).json()
    second, _ = owner(client, "thumbnail-other@example.com")

    response = client.get(f"/map/items/photo/{created_photo['id']}/thumbnail", headers=second)

    assert response.status_code == 404


def test_memory_map_thumbnail_is_empty(client: TestClient) -> None:
    headers, journey = owner(client)
    created_memory = memory(client, headers, journey["id"]).json()

    response = client.get(f"/map/items/memory/{created_memory['id']}/thumbnail", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"thumbnail_url": None}

    other, _ = owner(client, "memory-thumbnail-other@example.com")
    denied = client.get(f"/map/items/memory/{created_memory['id']}/thumbnail", headers=other)
    assert denied.status_code == 404
    assert (
        client.post(
            "/journeys",
            json={**journey_payload(), "latitude": 91, "longitude": 20},
            headers=headers,
        ).status_code
        == 422
    )
    journey = client.post("/journeys", json=journey_payload(), headers=headers).json()
    assert (
        client.patch(
            f"/journeys/{journey['id']}", json={"latitude": 41}, headers=headers
        ).status_code
        == 422
    )
