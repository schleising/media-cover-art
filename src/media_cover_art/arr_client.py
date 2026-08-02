"""Sync Sonarr / Radarr client for poster lookup."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx

from .config import ARR_LIBRARY_TTL_SECONDS, CoverArtSettings
from .identity import MediaIdentity
from .models import ArtProvider
from .title_match import pick_best_item_by_title

logger = logging.getLogger("media_cover_art.arr")


@dataclass(frozen=True)
class ArrPosterResult:
    """Poster URL resolved from Radarr or Sonarr."""

    provider: ArtProvider
    provider_id: str | None
    remote_url: str
    use_api_key: bool = False
    api_key: str | None = None
    matched_title: str | None = None


class _LibraryCache:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.fetched_at = 0.0

    def is_fresh(self) -> bool:
        return bool(self.items) and (time.monotonic() - self.fetched_at) < ARR_LIBRARY_TTL_SECONDS


class ArrClient:
    """Sync Radarr/Sonarr poster lookup using an injected settings object."""

    def __init__(self, settings: CoverArtSettings, http: httpx.Client) -> None:
        self._settings = settings
        self._http = http
        self._sonarr_cache = _LibraryCache()
        self._radarr_cache = _LibraryCache()

    def lookup_poster(self, identity: MediaIdentity) -> ArrPosterResult | None:
        """Look up a poster for film (Radarr) or TV (Sonarr).

        Args:
            identity: Parsed media identity.

        Returns:
            Poster result, or ``None`` if not found / not configured.
        """
        if identity.kind == "film":
            return self._lookup_radarr(identity)
        if identity.kind == "tv":
            return self._lookup_sonarr(identity)
        return None

    def download_image(
        self,
        url: str,
        *,
        api_key: str | None = None,
    ) -> tuple[bytes, str | None]:
        """Download poster bytes, enforcing the configured size cap.

        Args:
            url: Image URL.
            api_key: Optional Arr API key header for local URLs.

        Returns:
            ``(bytes, content_type)``.

        Raises:
            ValueError: Empty body or size exceeds ``max_poster_bytes``.
            httpx.HTTPError: On HTTP failure.
        """
        headers = {
            "Accept": "image/*,*/*",
            "User-Agent": self._settings.user_agent,
        }
        if api_key:
            headers["X-Api-Key"] = api_key
        response = self._http.get(url, headers=headers)
        response.raise_for_status()
        data = response.content
        if len(data) > self._settings.max_poster_bytes:
            raise ValueError(f"Poster exceeds {self._settings.max_poster_bytes} bytes")
        if not data:
            raise ValueError("Empty poster response")
        return data, response.headers.get("Content-Type")

    def _lookup_radarr(self, identity: MediaIdentity) -> ArrPosterResult | None:
        api_key = self._settings.radarr_api_key
        if not api_key:
            logger.warning(
                "Radarr API key not configured; film lookup skipped for %s",
                identity.cache_key,
            )
            return None
        base_url = self._settings.radarr_url.rstrip("/")
        library = self._get_library(
            kind="Radarr",
            base_url=base_url,
            api_key=api_key,
            path="/api/v3/movie",
            cache=self._radarr_cache,
        )
        item = find_item_by_title(library, identity.title, identity.year)
        if item is None:
            try:
                lookup = self._request_json(
                    base_url,
                    api_key,
                    "/api/v3/movie/lookup",
                    {"term": identity.title},
                )
                if isinstance(lookup, list):
                    item = find_item_by_title(
                        [entry for entry in lookup if isinstance(entry, dict)],
                        identity.title,
                        identity.year,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Radarr lookup failed for %s: %s", identity.title, exc)

        return self._poster_from_item(item, base_url, api_key, provider="radarr", id_keys=("tmdbId", "id"))

    def _lookup_sonarr(self, identity: MediaIdentity) -> ArrPosterResult | None:
        api_key = self._settings.sonarr_api_key
        if not api_key:
            logger.warning(
                "Sonarr API key not configured; TV lookup skipped for %s",
                identity.cache_key,
            )
            return None
        base_url = self._settings.sonarr_url.rstrip("/")
        library = self._get_library(
            kind="Sonarr",
            base_url=base_url,
            api_key=api_key,
            path="/api/v3/series",
            cache=self._sonarr_cache,
        )
        item = find_item_by_title(library, identity.title)
        if item is None:
            try:
                lookup = self._request_json(
                    base_url,
                    api_key,
                    "/api/v3/series/lookup",
                    {"term": identity.title},
                )
                if isinstance(lookup, list):
                    item = find_item_by_title(
                        [entry for entry in lookup if isinstance(entry, dict)],
                        identity.title,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sonarr lookup failed for %s: %s", identity.title, exc)

        return self._poster_from_item(
            item, base_url, api_key, provider="sonarr", id_keys=("tvdbId", "id")
        )

    def _poster_from_item(
        self,
        item: dict[str, Any] | None,
        base_url: str,
        api_key: str,
        *,
        provider: ArtProvider,
        id_keys: tuple[str, ...],
    ) -> ArrPosterResult | None:
        if item is None:
            return None
        images = item.get("images") if isinstance(item.get("images"), list) else None
        poster = find_poster(images)
        if poster is None:
            return None
        chosen = choose_download_url(base_url, poster, api_key)
        if chosen is None:
            return None
        url, use_api_key = chosen
        provider_id = None
        for key in id_keys:
            value = item.get(key)
            if value is not None and str(value):
                provider_id = str(value)
                break
        matched_title = str(item.get("title") or "") or None
        return ArrPosterResult(
            provider=provider,
            provider_id=provider_id,
            remote_url=url,
            use_api_key=use_api_key,
            api_key=api_key if use_api_key else None,
            matched_title=matched_title,
        )

    def _get_library(
        self,
        *,
        kind: str,
        base_url: str,
        api_key: str,
        path: str,
        cache: _LibraryCache,
    ) -> list[dict[str, Any]]:
        if cache.is_fresh():
            return cache.items
        try:
            payload = self._request_json(base_url, api_key, path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s library fetch failed: %s", kind, exc)
            return cache.items
        if not isinstance(payload, list):
            logger.warning("%s library response was not a list", kind)
            return cache.items
        cache.items = [item for item in payload if isinstance(item, dict)]
        cache.fetched_at = time.monotonic()
        return cache.items

    def _request_json(
        self,
        base_url: str,
        api_key: str,
        path: str,
        query: dict[str, str] | None = None,
    ) -> Any:
        url = f"{base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "User-Agent": self._settings.user_agent,
        }
        response = self._http.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def find_poster(images: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Prefer ``coverType=poster``, else the first image."""
    if not images:
        return None
    posters = [
        image
        for image in images
        if str(image.get("coverType", "")).lower() == "poster"
    ]
    if posters:
        return posters[0]
    return images[0] if images else None


def find_item_by_title(
    items: list[dict[str, Any]],
    title: str,
    year: int | None = None,
) -> dict[str, Any] | None:
    """Pick the best Arr library/lookup item by Policy C title match."""

    def candidate_titles(item: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for key in ("title", "sortTitle", "cleanTitle"):
            value = item.get(key)
            if value:
                values.append(str(value))
        return values

    def item_year(item: dict[str, Any]) -> int | None:
        value = item.get("year")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return pick_best_item_by_title(
        items,
        title,
        year,
        candidate_titles=candidate_titles,
        item_year=item_year,
    )


def _absolute_arr_url(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    if maybe_relative.startswith("http://") or maybe_relative.startswith("https://"):
        return maybe_relative
    return urljoin(base_url.rstrip("/") + "/", maybe_relative.lstrip("/"))


def choose_download_url(
    base_url: str,
    poster: dict[str, Any],
    api_key: str,
) -> tuple[str, bool] | None:
    """Prefer public ``remoteUrl``; else Arr local URL with apikey query."""
    remote = poster.get("remoteUrl")
    if isinstance(remote, str) and remote.strip():
        return remote.strip(), False

    local = _absolute_arr_url(
        base_url, poster.get("url") if isinstance(poster.get("url"), str) else None
    )
    if local is None:
        return None
    separator = "&" if "?" in local else "?"
    return f"{local}{separator}{urlencode({'apikey': api_key})}", True
