import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.journey import Journey
from app.models.media import Media
from tests.conftest import test_engine
from tests.helpers import auth_headers, journey_payload, login_user, register_user
from tests.test_media import upload_photo


def account(client, email):
    user = register_user(client, email=email)
    return user, auth_headers(login_user(client, email=email))


def journey(client, headers, visibility="private", title="A public journey"):
    response = client.post(
        "/journeys", headers=headers, json={**journey_payload(title), "visibility": visibility}
    )
    assert response.status_code == 201
    return response.json()


def test_visibility_default_and_validation(client: TestClient):
    _, owner = account(client, "owner@example.com")
    item = client.post("/journeys", headers=owner, json=journey_payload()).json()
    assert item["visibility"] == "private"
    for invalid in ("friends", None):
        assert (
            client.patch(
                f"/journeys/{item['id']}", headers=owner, json={"visibility": invalid}
            ).status_code
            == 422
        )
    assert (
        client.patch(
            f"/journeys/{item['id']}", headers=owner, json={"visibility": "public"}
        ).json()["visibility"]
        == "public"
    )
    assert client.get("/journeys", headers=owner).json()[0]["id"] == item["id"]


def test_discovery_excludes_own_and_private_and_limits_creator_data(client: TestClient):
    _, viewer = account(client, "viewer@example.com")
    owner_user, owner = account(client, "owner@example.com")
    journey(client, viewer, "public")
    journey(client, owner, "private")
    published = journey(client, owner, "public")
    response = client.get("/discover/journeys", headers=viewer)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert [item["id"] for item in data["items"]] == [published["id"]]
    assert data["next_cursor"] is None
    assert set(data["items"][0]["creator"]) == {"id", "username", "display_name", "avatar_url"}
    assert data["items"][0]["creator"]["id"] == owner_user["id"]
    assert "email" not in response.text
    assert "password_hash" not in response.text


def test_discovery_requires_auth(client: TestClient):
    assert client.get("/discover/journeys").status_code == 401
    assert client.get(f"/discover/journeys/{uuid.uuid4()}").status_code == 401


def test_cursor_pagination_stable_with_ties_and_new_items(client: TestClient):
    _, viewer = account(client, "viewer@example.com")
    _, owner = account(client, "owner@example.com")
    items = [journey(client, owner, "public", str(index)) for index in range(5)]
    with Session(test_engine) as session:
        for item in items:
            session.get(Journey, uuid.UUID(item["id"])).created_at = datetime(
                2025, 1, 1, tzinfo=UTC
            )
        session.commit()
    first = client.get("/discover/journeys?limit=2", headers=viewer).json()
    journey(client, owner, "public", "New after first page")
    ids = [item["id"] for item in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = client.get(
            "/discover/journeys", headers=viewer, params={"limit": 2, "cursor": cursor}
        ).json()
        ids.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert ids == sorted([item["id"] for item in items], reverse=True)
    assert len(set(ids)) == 5
    for params in ({"cursor": "not-a-cursor"}, {"limit": 0}, {"limit": 51}):
        assert client.get("/discover/journeys", headers=viewer, params=params).status_code == 422


def test_public_detail_and_private_revocation(client: TestClient):
    _, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    item = journey(client, owner, "public")
    photo = upload_photo(client, item["id"], owner).json()
    memory = client.post(
        f"/journeys/{item['id']}/memories",
        headers=owner,
        json={"title": "A quiet morning", "memory_date": "2025-03-12"},
    ).json()
    client.patch(f"/journeys/{item['id']}/cover/{photo['id']}", headers=owner)
    result = client.get(f"/discover/journeys/{item['id']}", headers=viewer)
    assert result.status_code == 200
    detail = result.json()
    assert detail["photos"][0]["id"] == photo["id"]
    assert detail["memories"][0]["id"] == memory["id"]
    assert detail["photo_count"] == detail["memory_count"] == 1
    assert detail["cover_media_url"].startswith("https://private-storage.test/")
    assert "expires=" in detail["photos"][0]["url"]
    assert "storage_key" not in result.text
    assert "original_filename" not in result.text
    # All existing owner endpoints stay owner-only, even for a public journey.
    for route in (
        f"/journeys/{item['id']}",
        f"/journeys/{item['id']}/media",
        f"/journeys/{item['id']}/memories",
    ):
        assert client.get(route, headers=viewer).status_code == 404
    assert (
        client.patch(
            f"/journeys/{item['id']}", headers=viewer, json={"visibility": "private"}
        ).status_code
        == 404
    )
    assert client.delete(f"/journeys/{item['id']}", headers=viewer).status_code == 404
    assert (
        client.patch(f"/journeys/{item['id']}/cover/{photo['id']}", headers=viewer).status_code
        == 404
    )
    assert (
        client.patch(
            f"/journeys/{item['id']}/media/{photo['id']}",
            headers=viewer,
            json={"caption": "Hacked"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/journeys/{item['id']}", headers=owner, json={"visibility": "private"}
        ).status_code
        == 200
    )
    assert client.get(f"/discover/journeys/{item['id']}", headers=viewer).status_code == 404
    assert client.get(f"/discover/journeys/{item['id']}", headers=owner).status_code == 200
    assert client.get("/discover/journeys", headers=viewer).json()["items"] == []


def test_pending_media_not_signed_or_counted(client: TestClient):
    _, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    item = journey(client, owner, "public")
    photo = upload_photo(client, item["id"], owner).json()
    client.patch(f"/journeys/{item['id']}/cover/{photo['id']}", headers=owner)
    with Session(test_engine) as session:
        session.get(Media, uuid.UUID(photo["id"])).deletion_pending_at = datetime.now(UTC)
        session.commit()
    detail = client.get(f"/discover/journeys/{item['id']}", headers=viewer).json()
    assert detail["cover_media_url"] is None
    assert detail["photos"] == []
    assert detail["photo_count"] == 0


@pytest.mark.parametrize("size", [1, 8])
def test_feed_query_count_is_constant(client: TestClient, size: int):
    _, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    for index in range(size):
        item = journey(client, owner, "public", str(index))
        photo = upload_photo(client, item["id"], owner).json()
        client.patch(f"/journeys/{item['id']}/cover/{photo['id']}", headers=owner)
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", capture)
    try:
        response = client.get("/discover/journeys", headers=viewer)
        assert response.status_code == 200
        assert len(response.json()["items"]) == size
    finally:
        event.remove(test_engine, "before_cursor_execute", capture)
    assert len(statements) == 5  # Auth + cards + two grouped counts + saved IDs.
