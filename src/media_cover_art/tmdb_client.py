"""Sync TMDB fallback for cover art."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import CoverArtSettings
from .identity import MediaIdentity
from .title_match import pick_best_item_by_title

logger = logging.getLogger("media_cover_art.tmdb")

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


@dataclass(frozen=True)
class TmdbPosterResult:
    """Poster URL resolved from TMDB."""

    provider_id: str
    remote_url: str
    matched_title: str | None = None
    provider: str = "tmdb"


class TmdbClient:
    """Sync TMDB search client."""

    def __init__(self, settings: CoverArtSettings, http: httpx.Client) -> None:
        self._settings = settings
        self._http = http

    def lookup_poster(self, identity: MediaIdentity) -> TmdbPosterResult | None:
        """Search TMDB for a film or TV poster.

        Args:
            identity: Parsed media identity.

        Returns:
            Poster result, or ``None`` if missing key / no match.
        """
        api_key = self._settings.tmdb_api_key
        if not api_key:
            return None
        if identity.kind == "film":
            return self._search_movie(api_key, identity)
        if identity.kind == "tv":
            return self._search_tv(api_key, identity)
        return None

    def download_image(self, url: str) -> tuple[bytes, str | None]:
        """Download a TMDB CDN image.

        Args:
            url: Absolute image URL.

        Returns:
            ``(bytes, content_type)``.
        """
        headers = {
            "Accept": "image/*,*/*",
            "User-Agent": self._settings.user_agent,
        }
        response = self._http.get(url, headers=headers)
        response.raise_for_status()
        data = response.content
        if len(data) > self._settings.max_poster_bytes:
            raise ValueError(f"Poster exceeds {self._settings.max_poster_bytes} bytes")
        if not data:
            raise ValueError("Empty poster response")
        return data, response.headers.get("Content-Type")

    def _search_movie(
        self, api_key: str, identity: MediaIdentity
    ) -> TmdbPosterResult | None:
        query: dict[str, str] = {"query": identity.title}
        if identity.year is not None:
            query["year"] = str(identity.year)
        payload = self._tmdb_get("/search/movie", api_key, query)
        if payload is None:
            return None
        results = payload.get("results")
        if not isinstance(results, list):
            return None
        item = _pick_result(
            [entry for entry in results if isinstance(entry, dict)],
            identity.title,
            identity.year,
            ("title", "original_title"),
            "release_date",
        )
        return _poster_from_item(item)

    def _search_tv(
        self, api_key: str, identity: MediaIdentity
    ) -> TmdbPosterResult | None:
        payload = self._tmdb_get("/search/tv", api_key, {"query": identity.title})
        if payload is None:
            return None
        results = payload.get("results")
        if not isinstance(results, list):
            return None
        item = _pick_result(
            [entry for entry in results if isinstance(entry, dict)],
            identity.title,
            identity.year,
            ("name", "original_name"),
            "first_air_date",
        )
        return _poster_from_item(item)

    def _tmdb_get(
        self,
        path: str,
        api_key: str,
        query: dict[str, str],
    ) -> dict[str, Any] | None:
        params = {"api_key": api_key, **query}
        url = f"{TMDB_API_BASE}{path}?{urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "User-Agent": self._settings.user_agent,
        }
        try:
            response = self._http.get(url, headers=headers)
            if response.status_code == 401:
                logger.warning("TMDB API key rejected")
                return None
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("TMDB request failed (%s): %s", path, exc)
            return None


def _pick_result(
    results: list[dict[str, Any]],
    title: str,
    year: int | None,
    title_keys: tuple[str, ...],
    date_key: str,
) -> dict[str, Any] | None:
    def candidate_titles(item: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for key in title_keys:
            value = item.get(key)
            if value:
                values.append(str(value))
        return values

    def item_year(item: dict[str, Any]) -> int | None:
        date_value = item.get(date_key)
        if isinstance(date_value, str) and len(date_value) >= 4 and date_value[:4].isdigit():
            return int(date_value[:4])
        return None

    return pick_best_item_by_title(
        results,
        title,
        year,
        candidate_titles=candidate_titles,
        item_year=item_year,
    )


def _poster_from_item(item: dict[str, Any] | None) -> TmdbPosterResult | None:
    if item is None:
        return None
    poster_path = item.get("poster_path")
    item_id = item.get("id")
    if not isinstance(poster_path, str) or not poster_path:
        return None
    if item_id is None:
        return None
    matched_title = None
    for key in ("name", "title", "original_name", "original_title"):
        value = item.get(key)
        if value:
            matched_title = str(value)
            break
    return TmdbPosterResult(
        provider_id=str(item_id),
        remote_url=f"{TMDB_IMAGE_BASE}{poster_path}",
        matched_title=matched_title,
    )
