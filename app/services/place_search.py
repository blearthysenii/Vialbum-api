import json
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError
from app.schemas.place import PlaceSearchResult

GEOAPIFY_SEARCH_URL = "https://api.geoapify.com/v1/geocode/search"


class PlaceProviderError(Exception):
    pass


class PlaceSearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[PlaceSearchResult]: ...


class UnconfiguredPlaceProvider:
    def search(self, _query: str, _limit: int) -> list[PlaceSearchResult]:
        raise ConfigurationError("Place search is not configured")


class GeoapifyPlaceProvider:
    def __init__(
        self,
        api_key: str,
        timeout: float,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.opener = opener

    def search(self, query: str, limit: int) -> list[PlaceSearchResult]:
        parameters = urlencode({"text": query, "limit": limit, "apiKey": self.api_key})
        url = f"{GEOAPIFY_SEARCH_URL}?{parameters}"
        try:
            with self.opener(
                Request(url, headers={"Accept": "application/json"}), timeout=self.timeout
            ) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise PlaceProviderError from exc
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise PlaceProviderError
        results: list[PlaceSearchResult] = []
        for feature in features:
            normalized = self._normalize(feature)
            if normalized is not None:
                results.append(normalized)
            if len(results) == limit:
                break
        return results

    @staticmethod
    def _normalize(feature: object) -> PlaceSearchResult | None:
        if not isinstance(feature, dict):
            return None
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            return None
        provider_id = properties.get("place_id")
        display_name = properties.get("formatted")
        name = properties.get("name") or properties.get("city") or properties.get("county")
        country = properties.get("country")
        country_code = properties.get("country_code")
        latitude = properties.get("lat")
        longitude = properties.get("lon")
        if not all((provider_id, display_name, name, country, country_code)):
            return None
        try:
            return PlaceSearchResult(
                provider="geoapify",
                provider_place_id=str(provider_id),
                display_name=str(display_name),
                name=str(name),
                locality=properties.get("city")
                or properties.get("town")
                or properties.get("village"),
                region=properties.get("state"),
                country=str(country),
                country_code=str(country_code),
                latitude=latitude,
                longitude=longitude,
            )
        except (TypeError, ValueError):
            return None


class PlaceSearchService:
    def __init__(self, provider: PlaceSearchProvider) -> None:
        self.provider = provider

    def search(self, query: str, limit: int) -> list[PlaceSearchResult]:
        try:
            return self.provider.search(query, limit)
        except PlaceProviderError as exc:
            raise ConfigurationError(
                "Place search is temporarily unavailable. Please try again."
            ) from exc


def get_place_search_provider() -> PlaceSearchProvider:
    settings = get_settings()
    if settings.geoapify_api_key is None:
        return UnconfiguredPlaceProvider()
    return GeoapifyPlaceProvider(
        settings.geoapify_api_key.get_secret_value(),
        settings.geoapify_timeout_seconds,
    )
