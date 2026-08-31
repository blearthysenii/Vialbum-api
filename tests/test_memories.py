import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.memory import Memory
from tests.conftest import test_engine
from tests.helpers import auth_headers, journey_payload, login_user, register_user

PAYLOAD = {
    "title": "Sunset",
    "caption": "By the water",
    "memory_date": "2025-03-14",
    "latitude": "41.123456",
    "longitude": "20.123456",
}


def setup(client):
    register_user(client)
    headers = auth_headers(login_user(client))
    journey = client.post("/journeys", json=journey_payload(), headers=headers).json()
    url = f"/journeys/{journey['id']}/memories"
    return headers, journey, url


def test_memory_crud(client: TestClient):
    headers, journey, url = setup(client)
    created = client.post(url, json=PAYLOAD, headers=headers)
    assert created.status_code == 201
    memory = created.json()
    assert memory["journey_id"] == journey["id"]
    assert memory["latitude"] == PAYLOAD["latitude"]
    assert memory["created_at"] and memory["updated_at"]
    item = f"{url}/{memory['id']}"
    assert client.get(item, headers=headers).json() == memory
    assert client.get(url, headers=headers).json() == [memory]
    updated = client.patch(item, json={"title": " New title ", "caption": None}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["title"] == "New title"
    assert updated.json()["caption"] is None
    assert updated.json()["memory_date"] == PAYLOAD["memory_date"]
    assert client.delete(item, headers=headers).status_code == 204
    assert client.get(item, headers=headers).status_code == 404
    assert client.get(url, headers=headers).json() == []


@pytest.mark.parametrize(
    "method,suffix",
    [("post", ""), ("get", ""), ("get", "/item"), ("patch", "/item"), ("delete", "/item")],
)
def test_memory_ownership_and_auth(client, method, suffix):
    headers, journey, url = setup(client)
    memory = client.post(url, json=PAYLOAD, headers=headers).json()
    target = url + (f"/{memory['id']}" if suffix else "")
    kwargs = {"json": PAYLOAD} if method in ("post", "patch") else {}
    assert getattr(client, method)(target, **kwargs).status_code == 401
    register_user(client, email="other@example.com")
    other = auth_headers(login_user(client, email="other@example.com"))
    assert getattr(client, method)(target, headers=other, **kwargs).status_code == 404
    own_journey = client.post("/journeys", json=journey_payload(), headers=other).json()
    if suffix:
        swapped = f"/journeys/{own_journey['id']}/memories/{memory['id']}"
        assert getattr(client, method)(swapped, headers=other, **kwargs).status_code == 404
    assert client.get(url, headers=headers).json() == [memory]


@pytest.mark.parametrize(
    "values",
    [
        {"title": "   "},
        {"title": None},
        {"memory_date": None},
        {"memory_date": "bad"},
        {"latitude": 91},
        {"longitude": -181},
    ],
)
def test_memory_validation(client, values):
    headers, _, url = setup(client)
    assert client.post(url, json={**PAYLOAD, **values}, headers=headers).status_code == 422
    memory = client.post(url, json=PAYLOAD, headers=headers).json()
    assert client.patch(f"{url}/{memory['id']}", json=values, headers=headers).status_code == 422


def test_memory_cannot_be_moved(client):
    headers, _, url = setup(client)
    memory = client.post(url, json=PAYLOAD, headers=headers).json()
    response = client.patch(
        f"{url}/{memory['id']}", json={"journey_id": str(uuid.uuid4())}, headers=headers
    )
    assert response.status_code == 422


def test_missing_journey(client):
    headers, _, _ = setup(client)
    url = f"/journeys/{uuid.uuid4()}/memories"
    assert client.get(url, headers=headers).status_code == 404
    assert client.post(url, json=PAYLOAD, headers=headers).status_code == 404


def test_memory_ordering(client):
    headers, journey, url = setup(client)
    ids = [uuid.UUID(int=i) for i in (3, 2, 1, 4)]
    with Session(test_engine) as session:
        for index, memory_id in enumerate(ids):
            session.add(
                Memory(
                    id=memory_id,
                    journey_id=uuid.UUID(journey["id"]),
                    title="Memory",
                    memory_date=datetime(2025, 3, 13 if index == 3 else 14).date(),
                    created_at=datetime(2025, 3, 14, 11 if index == 0 else 10, tzinfo=UTC),
                )
            )
        session.commit()
    assert [m["id"] for m in client.get(url, headers=headers).json()] == [
        str(ids[i]) for i in (3, 2, 1, 0)
    ]


def test_delete_memory_preserves_linked_photo_and_cover(client):
    from app.models.media import Media

    headers, journey, url = setup(client)
    memory = client.post(url, json=PAYLOAD, headers=headers).json()
    media_url = f"/journeys/{journey['id']}/media"
    photo = client.post(
        media_url,
        headers=headers,
        files={"file": ("photo.jpg", b"\xff\xd8\xff\xe0photo", "image/jpeg")},
    ).json()
    with Session(test_engine) as session:
        stored = session.get(Media, uuid.UUID(photo["id"]))
        stored.memory_id = uuid.UUID(memory["id"])
        session.commit()
    cover_url = f"/journeys/{journey['id']}/cover/{photo['id']}"
    assert client.patch(cover_url, headers=headers).status_code == 200
    assert client.delete(f"{url}/{memory['id']}", headers=headers).status_code == 204
    photos = client.get(media_url, headers=headers).json()
    assert len(photos) == 1 and photos[0]["memory_id"] is None
    assert (
        client.get(f"/journeys/{journey['id']}", headers=headers).json()["cover_media_id"]
        == photo["id"]
    )
