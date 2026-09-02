from fastapi.testclient import TestClient

from tests.helpers import auth_headers, journey_payload, login_user, register_user
from tests.test_media import PLACE_SELECTION, upload_photo


def setup_library(
    client: TestClient, email: str = "search@example.com"
) -> tuple[dict[str, str], dict]:
    register_user(client, email=email)
    headers = auth_headers(login_user(client, email=email))
    payload = journey_payload("Medina Reflections")
    payload["description"] = "Quiet courtyards and evening prayers"
    payload["place"] = PLACE_SELECTION
    journey = client.post("/journeys", json=payload, headers=headers).json()
    return headers, journey


def add_memory(
    client: TestClient, headers: dict[str, str], journey: dict, title: str, caption: str
):
    return client.post(
        f"/journeys/{journey['id']}/memories",
        json={"title": title, "caption": caption, "memory_date": "2025-03-14"},
        headers=headers,
    ).json()


def test_search_requires_authentication(client: TestClient) -> None:
    assert client.get("/search", params={"q": "medina"}).status_code == 401


def test_searches_journey_title_destination_description_and_place(client: TestClient) -> None:
    headers, _journey = setup_library(client)
    for query in ("reflections", "medin", "courtyard", "madinah"):
        response = client.get("/search", params={"q": query}, headers=headers)
        assert response.status_code == 200
        assert len(response.json()["journeys"]) == 1


def test_searches_memory_title_notes_and_normalized_place(client: TestClient) -> None:
    headers, journey = setup_library(client)
    memory = add_memory(client, headers, journey, "The old mosque", "A peaceful afternoon")
    client.patch(
        f"/journeys/{journey['id']}/memories/{memory['id']}",
        json={"place": PLACE_SELECTION},
        headers=headers,
    )
    for query in ("mosq", "PEACEFUL", "Saudi"):
        body = client.get("/search", params={"q": query}, headers=headers).json()
        assert body["memories"][0]["id"] == memory["id"]
        assert body["memories"][0]["journey_title"] == journey["title"]


def test_searches_photo_caption_place_and_memory_context(client: TestClient) -> None:
    headers, journey = setup_library(client)
    memory = add_memory(client, headers, journey, "Blue mosque", "Under the arches")
    photo = upload_photo(client, journey["id"], headers).json()
    client.patch(
        f"/journeys/{journey['id']}/media/{photo['id']}",
        json={"caption": "Golden minaret", "place": PLACE_SELECTION, "memory_id": memory["id"]},
        headers=headers,
    )
    for query in ("gold", "Madinah", "arches"):
        body = client.get("/search", params={"q": query}, headers=headers).json()
        assert body["photos"][0]["id"] == photo["id"]
        assert body["photos"][0]["thumbnail_url"].startswith("https://private-storage.test/")


def test_search_is_case_insensitive_partial_and_ranks_titles(client: TestClient) -> None:
    headers, journey = setup_library(client)
    secondary = add_memory(client, headers, journey, "Courtyard", "Medina")
    word = add_memory(client, headers, journey, "An evening in Medina", "Warm light")
    prefix = add_memory(client, headers, journey, "Medina sunset", "Warm light")
    exact = add_memory(client, headers, journey, "Medina", "Arrival")
    results = client.get("/search", params={"q": "mEDIna"}, headers=headers).json()["memories"]
    assert [item["id"] for item in results[:4]] == [
        exact["id"],
        prefix["id"],
        word["id"],
        secondary["id"],
    ]


def test_search_never_returns_another_users_content(client: TestClient) -> None:
    owner, journey = setup_library(client, "owner-search@example.com")
    add_memory(client, owner, journey, "Private mosque", "Private Medina notes")
    intruder, _ = setup_library(client, "intruder-search@example.com")
    response = client.get("/search", params={"q": "private"}, headers=intruder).json()
    assert response["journeys"] == []
    assert response["memories"] == []
    assert response["photos"] == []


def test_search_limits_each_result_type(client: TestClient) -> None:
    headers, journey = setup_library(client)
    for index in range(14):
        add_memory(client, headers, journey, f"Mosque {index}", "Shared term")
    body = client.get("/search", params={"q": "mosque"}, headers=headers).json()
    assert len(body["memories"]) == 10


def test_search_validates_query_and_returns_empty_groups(client: TestClient) -> None:
    headers, _journey = setup_library(client)
    for query in ("x", "   "):
        assert client.get("/search", params={"q": query}, headers=headers).status_code == 422
    assert client.get("/search", params={"q": "x" * 101}, headers=headers).status_code == 422
    body = client.get("/search", params={"q": "unfindable"}, headers=headers).json()
    assert body["journeys"] == [] and body["memories"] == [] and body["photos"] == []
