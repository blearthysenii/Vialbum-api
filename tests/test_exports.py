import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.exports import ExportService
from tests.conftest import FakeObjectStorage
from tests.helpers import auth_headers, journey_payload, login_user, register_user
from tests.test_media import JPEG, PLACE_SELECTION


def library(client: TestClient, email: str = "export@example.com") -> tuple[dict[str, str], dict]:
    register_user(client, email=email)
    headers = auth_headers(login_user(client, email=email))
    payload = journey_payload("Medina / 2025")
    payload.update({"place": PLACE_SELECTION, "latitude": "24.500000", "longitude": "39.700000"})
    journey = client.post("/journeys", json=payload, headers=headers).json()
    memory = client.post(
        f"/journeys/{journey['id']}/memories",
        json={
            "title": "Courtyard",
            "caption": "Quiet afternoon",
            "memory_date": "2025-03-14",
            "place": PLACE_SELECTION,
        },
        headers=headers,
    ).json()
    return headers, {**journey, "memory": memory}


def photo(
    client: TestClient, headers: dict[str, str], journey: dict, name: str = "photo.jpg"
) -> dict:
    uploaded = client.post(
        f"/journeys/{journey['id']}/media",
        headers=headers,
        files={"file": (name, JPEG, "image/jpeg")},
        data={
            "captured_at": "2025-03-14T10:00:00Z",
            "latitude": "24.510000",
            "longitude": "39.710000",
        },
    ).json()
    return client.patch(
        f"/journeys/{journey['id']}/media/{uploaded['id']}",
        headers=headers,
        json={
            "caption": "Golden light",
            "memory_id": journey["memory"]["id"],
            "place": PLACE_SELECTION,
        },
    ).json()


def archive(response) -> zipfile.ZipFile:
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    return zipfile.ZipFile(io.BytesIO(response.content))


def read_json(bundle: zipfile.ZipFile, suffix: str) -> dict:
    name = next(name for name in bundle.namelist() if name.endswith(suffix))
    return json.loads(bundle.read(name))


def test_journey_export_requires_authentication_and_ownership(client: TestClient) -> None:
    owner, journey = library(client)
    assert client.get(f"/journeys/{journey['id']}/export").status_code == 401
    register_user(client, email="other-export@example.com")
    other = auth_headers(login_user(client, email="other-export@example.com"))
    assert client.get(f"/journeys/{journey['id']}/export", headers=other).status_code == 404
    assert client.get(f"/journeys/{journey['id']}/export", headers=owner).status_code == 200


def test_journey_data_only_export_is_complete_and_portable(client: TestClient) -> None:
    headers, journey = library(client)
    item = photo(client, headers, journey)
    with archive(
        client.get(f"/journeys/{journey['id']}/export?include_media=false", headers=headers)
    ) as bundle:
        journey_json = read_json(bundle, "/journey.json")
        memories = read_json(bundle, "/memories.json")["memories"]
        media = read_json(bundle, "/media.json")["media"]
        assert journey_json["export_version"] == 1
        assert journey_json["place"]["name"] == "Medina"
        assert memories[0]["caption"] == "Quiet afternoon"
        assert media[0]["caption"] == "Golden light"
        assert media[0]["captured_at"].startswith("2025-03-14T10:00:00")
        assert media[0]["memory_id"] == journey["memory"]["id"]
        assert media[0]["latitude"] == "24.468600"
        assert media[0]["exported_file"] is None
        assert not any("/photos/" in name for name in bundle.namelist())
        assert "storage_key" not in json.dumps(media)
        assert item["id"] == media[0]["id"]


def test_journey_export_includes_original_media_with_safe_duplicate_names(
    client: TestClient,
) -> None:
    headers, journey = library(client)
    photo(client, headers, journey, "../same.jpg")
    photo(client, headers, journey, "same.jpg")
    with archive(client.get(f"/journeys/{journey['id']}/export", headers=headers)) as bundle:
        paths = [name for name in bundle.namelist() if "/photos/" in name]
        assert len(paths) == 2
        assert len(set(paths)) == 2
        assert all(".." not in name and name.endswith(".jpg") for name in paths)
        assert all(
            item["exported_variant"] == "original"
            for item in read_json(bundle, "/media.json")["media"]
        )


def test_missing_media_is_recorded_without_failing_export(
    client: TestClient, fake_storage: FakeObjectStorage
) -> None:
    headers, journey = library(client)
    photo(client, headers, journey)
    fake_storage.objects.clear()
    with archive(client.get(f"/journeys/{journey['id']}/export", headers=headers)) as bundle:
        item = read_json(bundle, "/media.json")["media"][0]
        assert item["exported_file"] is None
        assert "unavailable" in item["export_error"]


def test_account_export_is_owned_structured_data_without_secrets(client: TestClient) -> None:
    headers, journey = library(client)
    photo(client, headers, journey)
    other, other_journey = library(client, "separate-export@example.com")
    photo(client, other, other_journey)
    with archive(client.get("/account/export", headers=headers)) as bundle:
        serialized = b"".join(bundle.read(name) for name in bundle.namelist()).decode()
        assert journey["id"] in serialized
        assert other_journey["id"] not in serialized
        assert "Medina" in serialized
        for forbidden in (
            "password_hash",
            "refresh_sessions",
            "token_hash",
            "storage_key",
            "secret",
        ):
            assert forbidden not in serialized


def test_account_export_requires_authentication(client: TestClient) -> None:
    assert client.get("/account/export").status_code == 401


def test_response_and_generation_failure_cleanup_temporary_files(client: TestClient) -> None:
    headers, journey = library(client)
    with tempfile.TemporaryDirectory() as directory:
        completed = Path(directory) / "complete.zip"
        with patch.object(ExportService, "_temporary_path", return_value=completed):
            assert (
                client.get(f"/journeys/{journey['id']}/export", headers=headers).status_code == 200
            )
        assert not completed.exists()

        failed = Path(directory) / "failed.zip"
        with (
            patch.object(ExportService, "_temporary_path", return_value=failed),
            patch("app.services.exports.zipfile.ZipFile", side_effect=RuntimeError("zip failed")),
        ):
            with pytest.raises(RuntimeError, match="zip failed"):
                client.get(f"/journeys/{journey['id']}/export", headers=headers)
        assert not failed.exists()


def test_export_safeguards_reject_declared_oversize(client: TestClient) -> None:
    headers, journey = library(client)
    photo(client, headers, journey)
    with patch("app.services.exports.MAX_DECLARED_MEDIA_BYTES", 1):
        response = client.get(f"/journeys/{journey['id']}/export", headers=headers)
    assert response.status_code == 422
