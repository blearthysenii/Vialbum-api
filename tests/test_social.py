import uuid

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models.saved_journey import SavedJourney
from app.models.user import User
from tests.conftest import test_engine
from tests.test_discover import account, journey


def test_public_profile_fields_counts_avatar_and_missing_user(client):
    owner, headers = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    public = journey(client, headers, "public")
    journey(client, headers, "private")
    with Session(test_engine) as session:
        session.get(User, uuid.UUID(owner["id"])).profile_photo_storage_key = "avatar/photo.jpg"
        session.commit()
    response = client.get(f"/users/{owner['id']}/public-profile", headers=viewer)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "id",
        "username",
        "display_name",
        "first_name",
        "last_name",
        "bio",
        "location",
        "avatar_url",
        "public_journeys_count",
        "cover_url",
        "is_following",
    }
    assert data["public_journeys_count"] == 1
    assert data["avatar_url"].startswith("https://private-storage.test/")
    assert "expires=" in data["avatar_url"]
    for auth in (headers, viewer):
        result = client.get(f"/users/{owner['id']}/public-journeys", headers=auth).json()
        assert [item["id"] for item in result["items"]] == [public["id"]]
    for suffix in ("public-profile", "public-journeys"):
        assert client.get(f"/users/{uuid.uuid4()}/{suffix}", headers=viewer).status_code == 404


def test_save_unsave_idempotent_and_scoped(client):
    _, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    _, other = account(client, "other@example.com")
    item = journey(client, owner, "public")
    url = f"/journeys/{item['id']}/save"
    for _ in range(2):
        assert client.post(url, headers=viewer).status_code == 204
    with Session(test_engine) as session:
        assert session.scalar(select(func.count(SavedJourney.id))) == 1
    assert client.get("/discover/journeys", headers=viewer).json()["items"][0]["is_saved"]
    assert client.get(f"/discover/journeys/{item['id']}", headers=viewer).json()["is_saved"]
    assert not client.get(f"/discover/journeys/{item['id']}", headers=other).json()["is_saved"]
    assert client.delete(url, headers=other).status_code == 204
    assert len(client.get("/saved/journeys", headers=viewer).json()["items"]) == 1
    for _ in range(2):
        assert client.delete(url, headers=viewer).status_code == 204
    assert client.get("/saved/journeys", headers=viewer).json()["items"] == []
    assert not client.get(f"/discover/journeys/{item['id']}", headers=viewer).json()["is_saved"]


def test_save_private_own_missing_rejected(client):
    _, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    private = journey(client, owner)
    own = journey(client, viewer, "public")
    for identifier in (private["id"], own["id"], str(uuid.uuid4())):
        assert client.post(f"/journeys/{identifier}/save", headers=viewer).status_code == 404
    assert client.get("/saved/journeys", headers=viewer).json()["items"] == []


def test_required_two_account_privacy_scenario(client):
    a, a_headers = account(client, "account_a@example.com")
    _, b = account(client, "account_b@example.com")
    item = journey(client, a_headers, "public")
    journey(client, a_headers, "private")
    assert client.get("/discover/journeys", headers=b).json()["items"][0]["id"] == item["id"]
    profile_url = f"/users/{a['id']}/public-profile"
    journeys_url = f"/users/{a['id']}/public-journeys"
    assert client.get(profile_url, headers=b).json()["public_journeys_count"] == 1
    assert len(client.get(journeys_url, headers=b).json()["items"]) == 1
    save_url = f"/journeys/{item['id']}/save"
    assert client.post(save_url, headers=b).status_code == 204
    assert client.get("/saved/journeys", headers=b).json()["items"][0]["id"] == item["id"]
    assert client.get(f"/discover/journeys/{item['id']}", headers=b).json()["is_saved"]
    assert client.delete(save_url, headers=b).status_code == 204
    assert client.get("/saved/journeys", headers=b).json()["items"] == []
    # Retain a stale save to prove privacy filtering applies to relationships too.
    assert client.post(save_url, headers=b).status_code == 204
    assert (
        client.patch(
            f"/journeys/{item['id']}", headers=a_headers, json={"visibility": "private"}
        ).status_code
        == 200
    )
    for url in ("/discover/journeys", journeys_url, "/saved/journeys"):
        assert client.get(url, headers=b).json()["items"] == []
    assert client.get(profile_url, headers=b).json()["public_journeys_count"] == 0
    assert client.get(f"/discover/journeys/{item['id']}", headers=b).status_code == 404
    assert client.post(save_url, headers=b).status_code == 404
    assert client.delete(save_url, headers=b).status_code == 204


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/users/{id}/public-profile"),
        ("get", "/users/{id}/public-journeys"),
        ("post", "/journeys/{id}/save"),
        ("delete", "/journeys/{id}/save"),
        ("get", "/saved/journeys"),
    ],
)
def test_social_requires_auth(client, method, path):
    assert getattr(client, method)(path.format(id=uuid.uuid4())).status_code == 401


def test_public_and_saved_pagination(client):
    owner, auth = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    items = [journey(client, auth, "public", str(i)) for i in range(5)]
    for item in items:
        assert client.post(f"/journeys/{item['id']}/save", headers=viewer).status_code == 204
    for url in (f"/users/{owner['id']}/public-journeys", "/saved/journeys"):
        seen, cursor = [], None
        while True:
            response = client.get(
                url, headers=viewer, params={"limit": 2, **({"cursor": cursor} if cursor else {})}
            )
            assert response.status_code == 200
            page = response.json()
            assert len(page["items"]) <= 2
            assert all(item["is_saved"] for item in page["items"])
            seen.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert seen == [item["id"] for item in reversed(items)]
        for params in ({"limit": 0}, {"limit": 51}, {"cursor": "invalid"}):
            assert client.get(url, headers=viewer, params=params).status_code == 422


def test_saved_relationship_cascades_on_journey_deletion(client):
    _, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    item = journey(client, owner, "public")
    assert client.post(f"/journeys/{item['id']}/save", headers=viewer).status_code == 204
    assert client.delete(f"/journeys/{item['id']}", headers=owner).status_code == 204
    with Session(test_engine) as session:
        assert session.scalar(select(func.count(SavedJourney.id))) == 0


@pytest.mark.parametrize("size", [1, 8])
def test_social_lists_have_constant_query_counts(client, size):
    owner_user, owner = account(client, "owner@example.com")
    _, viewer = account(client, "viewer@example.com")
    for index in range(size):
        item = journey(client, owner, "public", str(index))
        assert client.post(f"/journeys/{item['id']}/save", headers=viewer).status_code == 204
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", capture)
    try:
        for url, count in (
            ("/saved/journeys", 5),
            (f"/users/{owner_user['id']}/public-journeys", 6),
        ):
            statements.clear()
            response = client.get(url, headers=viewer)
            assert response.status_code == 200
            assert len(response.json()["items"]) == size
            assert len(statements) == count
    finally:
        event.remove(test_engine, "before_cursor_execute", capture)
