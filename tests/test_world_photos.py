import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models.media import Media, MediaType
from app.models.memory import Memory
from app.models.place import Place
from tests.conftest import test_engine
from tests.helpers import journey_payload
from tests.test_discover import account
from tests.test_world import WORLD, get_map, visit


def scenario(client):
    _, auth = account(client, "world@example.com")
    berlin = visit(client, auth, "Berlin", 52.52, 13.4, code="DE", country="Germany")
    saudi = client.post("/journeys", headers=auth, json=journey_payload("Saudi Arabia")).json()
    with Session(test_engine) as session:
        for name, lat, lon, count in [("Medina", 24.47, 39.61, 3), ("Makkah", 21.42, 39.82, 2)]:
            place = Place(
                provider="geoapify",
                provider_place_id=name,
                name=name,
                display_name=name,
                locality=name,
                country="Saudi Arabia",
                country_code="SA",
                latitude=lat,
                longitude=lon,
            )
            session.add(place)
            session.flush()
            memory = Memory(
                journey_id=uuid.UUID(saudi["id"]),
                place_id=place.id,
                title="IMG_2828",
                memory_date=date(2025, 1, 1),
            )
            session.add(memory)
            session.flush()
            for n in range(count):
                session.add(
                    Media(
                        journey_id=memory.journey_id,
                        memory_id=memory.id,
                        place_id=place.id,
                        type=MediaType.photo,
                        storage_key=f"{name}/{n}",
                        original_filename="DSC_8383.jpg",
                        caption="img_jndjd",
                        mime_type="image/jpeg",
                        file_size=100,
                        latitude=0,
                        longitude=0,
                        captured_at=datetime(2025, 1, n + 1, tzinfo=UTC),
                    )
                )
        for n in range(2):
            session.add(
                Media(
                    journey_id=uuid.UUID(berlin["id"]),
                    type=MediaType.photo,
                    storage_key=f"berlin/{n}",
                    mime_type="image/jpeg",
                    file_size=100,
                )
            )
        session.add(
            Media(
                journey_id=uuid.UUID(saudi["id"]),
                type=MediaType.photo,
                storage_key="no-location",
                mime_type="image/jpeg",
                file_size=100,
            )
        )
        session.commit()
    return auth


def test_real_places_and_photo_counts(client):
    auth = scenario(client)
    world = get_map(client, auth, True)
    assert {p["name"] for p in world["items"]} == {"Berlin", "Medina", "Makkah"}
    assert world["stats"] == {"journeys": 2, "countries": 2, "cities": 3, "places": 3}
    assert {p["name"]: p["photo_count"] for p in world["items"]} == {
        "Berlin": 2,
        "Medina": 3,
        "Makkah": 2,
    }
    assert world["bounds"]["north"] == 52.52
    assert world["bounds"]["south"] == 21.42
    for place in world["items"]:
        detail = client.get(f"/users/me/world/places/{place['id']}", headers=auth).json()
        assert detail["journey_count"] == 1
        assert len(detail["journeys"]) == 1


def test_viewport_names_numbering_and_privacy(client):
    auth = scenario(client)
    url = "/users/me/world/photos"
    response = client.get(url, headers=auth, params=WORLD)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    all_photos = response.json()["items"]
    assert len(all_photos) == 7
    params = {**WORLD, "north": 25, "south": 24, "west": 39, "east": 40}
    photos = client.get(url, headers=auth, params=params).json()["items"]
    assert [p["display_name"] for p in photos] == [f"Medina Photo {n}" for n in range(1, 4)]
    assert all(p["latitude"] == 24.47 and p["memory_id"] for p in photos)
    assert [p["display_name"] for p in all_photos if p["place_name"] == "Medina"] == [
        p["display_name"] for p in photos
    ]
    assert all("original_filename" not in p and "storage_key" not in p for p in photos)
    assert client.get(url, headers=auth, params={**params, "limit": 1}).json()["truncated"]
    _, other = account(client, "other-world@example.com")
    assert client.get(url, headers=other, params=WORLD).json()["items"] == []
    assert get_map(client, other, True)["items"] == []
    assert client.get(url, params=WORLD).status_code == 401
