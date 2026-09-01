import io
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.place import PlaceSearchResult
from app.services.place_search import (
    GeoapifyPlaceProvider,
    PlaceProviderError,
    get_place_search_provider,
)
from tests.helpers import auth_headers, login_user, register_user

PLACE = PlaceSearchResult(
    provider="geoapify",
    provider_place_id="place-medina",
    display_name="Medina, Al Madinah, Saudi Arabia",
    name="Medina",
    locality="Medina",
    region="Al Madinah",
    country="Saudi Arabia",
    country_code="SA",
    latitude=Decimal("24.468600"),
    longitude=Decimal("39.614200"),
)


class FakeProvider:
    def __init__(self, results: list[PlaceSearchResult] | None = None) -> None:
        self.results = results or []
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> list[PlaceSearchResult]:
        self.queries.append((query, limit))
        return self.results[:limit]


def headers(client: TestClient) -> dict[str, str]:
    register_user(client)
    return auth_headers(login_user(client))


def test_place_search_requires_authentication(client: TestClient) -> None:
    assert client.get("/places/search", params={"q": "Medina"}).status_code == 401


@pytest.mark.parametrize("query", ["M", "  "])
def test_place_search_rejects_short_queries(client: TestClient, query: str) -> None:
    assert (
        client.get("/places/search", params={"q": query}, headers=headers(client)).status_code
        == 422
    )


def test_place_search_caps_results_and_does_not_leak_provider_payload(
    client: TestClient,
) -> None:
    provider = FakeProvider([PLACE] * 10)
    app.dependency_overrides[get_place_search_provider] = lambda: provider
    try:
        response = client.get("/places/search", params={"q": "Medina"}, headers=headers(client))
    finally:
        app.dependency_overrides.pop(get_place_search_provider, None)
    assert response.status_code == 200
    assert len(response.json()) == 6
    assert provider.queries == [("Medina", 6)]
    assert set(response.json()[0]) == {
        "provider",
        "provider_place_id",
        "display_name",
        "name",
        "locality",
        "region",
        "country",
        "country_code",
        "latitude",
        "longitude",
    }


class JsonResponse(io.BytesIO):
    def __enter__(self) -> "JsonResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_geoapify_provider_normalizes_valid_features() -> None:
    payload = {
        "features": [
            {
                "properties": {
                    "place_id": "abc",
                    "formatted": "Milan, Lombardy, Italy",
                    "name": "Milan",
                    "city": "Milan",
                    "state": "Lombardy",
                    "country": "Italy",
                    "country_code": "it",
                    "lat": 45.4642035,
                    "lon": 9.1900127,
                    "raw": "must not escape",
                }
            }
        ]
    }
    provider = GeoapifyPlaceProvider(
        "secret", 1, opener=lambda *_args, **_kwargs: JsonResponse(json.dumps(payload).encode())
    )
    result = provider.search("Milan", 5)
    assert result[0].country_code == "IT"
    assert result[0].latitude == Decimal("45.464204")
    assert result[0].longitude == Decimal("9.190013")
    assert "raw" not in result[0].model_dump()


def test_geoapify_provider_skips_malformed_features() -> None:
    payload = {"features": [{"properties": {"place_id": "missing-fields"}}, "bad"]}
    provider = GeoapifyPlaceProvider(
        "secret", 1, opener=lambda *_args, **_kwargs: JsonResponse(json.dumps(payload).encode())
    )
    assert provider.search("Milan", 5) == []


def test_geoapify_provider_wraps_timeout() -> None:
    def timeout(*_args: object, **_kwargs: object) -> object:
        raise TimeoutError

    with pytest.raises(PlaceProviderError):
        GeoapifyPlaceProvider("secret", 0.01, opener=timeout).search("Milan", 5)


def test_place_search_returns_service_unavailable_on_provider_failure(client: TestClient) -> None:
    class FailingProvider:
        def search(self, _query: str, _limit: int) -> list[PlaceSearchResult]:
            raise PlaceProviderError

    app.dependency_overrides[get_place_search_provider] = FailingProvider
    try:
        response = client.get("/places/search", params={"q": "Milan"}, headers=headers(client))
    finally:
        app.dependency_overrides.pop(get_place_search_provider, None)
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
