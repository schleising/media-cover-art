"""Configuration and settings for media cover art."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_SONARR_URL = "http://steveds920:8989"
DEFAULT_RADARR_URL = "http://steveds920:7878"
DEFAULT_PLACEHOLDER_ART_URL = "/icons/tools/converter/art-placeholder.svg"
MISSING_TTL_SECONDS = 7 * 24 * 60 * 60
ERROR_TTL_SECONDS = 2 * 60
ARR_LIBRARY_TTL_SECONDS = 30 * 60
READY_RETENTION_SECONDS = 14 * 24 * 60 * 60
PURGE_INTERVAL_SECONDS = 6 * 60 * 60
MAX_POSTER_BYTES = 5 * 1024 * 1024

_KEY_FILE_CANDIDATES = (
    Path("/run/secrets/arr-keys.txt"),
    Path("/app/secrets/arr-keys.txt"),
)


@dataclass(frozen=True)
class CoverArtSettings:
    """Runtime settings for :class:`~media_cover_art.client.CoverArtClient`.

    Attributes:
        sonarr_url: Sonarr base URL.
        radarr_url: Radarr base URL.
        sonarr_api_key: Sonarr API key, if configured.
        radarr_api_key: Radarr API key, if configured.
        tmdb_api_key: TMDB API key, if configured.
        mongo_uri: MongoDB connection URI.
        mongo_db: Database name (default ``media``).
        mongo_collection: Cover-art collection name.
        cache_dir: Optional local poster directory; ``None`` = metadata-only.
        placeholder_art_url: URL returned when art is not ready locally.
        missing_ttl_seconds: Negative-cache TTL for ``missing``.
        error_ttl_seconds: Negative-cache TTL for ``error``.
        ready_retention_seconds: Unused ready-row retention before purge.
        max_poster_bytes: Maximum accepted poster download size.
        user_agent: HTTP User-Agent for Arr/TMDB requests.
        connect_timeout_seconds: HTTP connect timeout.
        read_timeout_seconds: HTTP read timeout.
    """

    sonarr_url: str = DEFAULT_SONARR_URL
    radarr_url: str = DEFAULT_RADARR_URL
    sonarr_api_key: str | None = None
    radarr_api_key: str | None = None
    tmdb_api_key: str | None = None
    mongo_uri: str = "mongodb://localhost:27017/"
    mongo_db: str = "media"
    mongo_collection: str = "cover_art_cache"
    cache_dir: Path | None = None
    placeholder_art_url: str = DEFAULT_PLACEHOLDER_ART_URL
    missing_ttl_seconds: int = MISSING_TTL_SECONDS
    error_ttl_seconds: int = ERROR_TTL_SECONDS
    ready_retention_seconds: int = READY_RETENTION_SECONDS
    max_poster_bytes: int = MAX_POSTER_BYTES
    user_agent: str = "media-cover-art/1.0"
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0

    @classmethod
    def from_env(
        cls,
        *,
        keys_file: Path | str | None = None,
        cache_dir: Path | str | None = None,
    ) -> CoverArtSettings:
        """Build settings from environment variables and optional keys file.

        Recognizes ``MEDIA_COVER_ART_*`` names with aliases for existing
        ``CONVERTER_ART_*`` / Arr env vars used by website3.

        Args:
            keys_file: Optional explicit path to ``key=value`` secrets file.
            cache_dir: Optional override for the local cache directory.

        Returns:
            Populated settings instance.
        """
        keys = load_arr_keys(keys_file)
        resolved_cache = cache_dir
        if resolved_cache is None:
            raw_cache = _first_env(
                "MEDIA_COVER_ART_CACHE_DIR",
                "CONVERTER_ART_CACHE_DIR",
            )
            resolved_cache = Path(raw_cache) if raw_cache else None
        elif isinstance(resolved_cache, str):
            resolved_cache = Path(resolved_cache)

        mongo_uri = _first_env(
            "MEDIA_COVER_ART_MONGO_URI",
            "DB_URL",
            default="mongodb://localhost:27017/",
        )
        assert mongo_uri is not None

        return cls(
            sonarr_url=_first_env("SONARR_URL", default=DEFAULT_SONARR_URL)
            or DEFAULT_SONARR_URL,
            radarr_url=_first_env("RADARR_URL", default=DEFAULT_RADARR_URL)
            or DEFAULT_RADARR_URL,
            sonarr_api_key=_first_env("SONARR_API_KEY") or keys.get("sonarr_key"),
            radarr_api_key=_first_env("RADARR_API_KEY") or keys.get("radarr_key"),
            tmdb_api_key=(
                _first_env("TMDB_API_KEY")
                or keys.get("tmdb_key")
                or keys.get("tmdb_api_key")
            ),
            mongo_uri=mongo_uri,
            mongo_db=_first_env("MEDIA_COVER_ART_MONGO_DB", "DB_NAME", default="media")
            or "media",
            mongo_collection=_first_env(
                "MEDIA_COVER_ART_MONGO_COLLECTION",
                default="cover_art_cache",
            )
            or "cover_art_cache",
            cache_dir=resolved_cache,
            placeholder_art_url=_first_env(
                "MEDIA_COVER_ART_PLACEHOLDER_URL",
                default=DEFAULT_PLACEHOLDER_ART_URL,
            )
            or DEFAULT_PLACEHOLDER_ART_URL,
        )

    @classmethod
    def from_keys_file(
        cls,
        path: Path | str,
        **overrides: object,
    ) -> CoverArtSettings:
        """Build settings from a keys file, then apply keyword overrides.

        Args:
            path: Path to ``key=value`` secrets file.
            **overrides: Fields to override on the resulting settings.

        Returns:
            Settings with keys loaded and overrides applied.
        """
        base = cls.from_env(keys_file=path)
        if not overrides:
            return base
        payload = {**base.__dict__, **overrides}
        return cls(**payload)  # type: ignore[arg-type]


def load_arr_keys(keys_file: Path | str | None = None) -> dict[str, str]:
    """Load ``key=value`` pairs from an Arr keys file.

    Args:
        keys_file: Explicit path, or search default candidate paths.

    Returns:
        Mapping of key names to values (empty if no file found).
    """
    candidates: list[Path] = []
    if keys_file is not None:
        candidates.append(Path(keys_file))
    candidates.extend(_KEY_FILE_CANDIDATES)

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            return _parse_keys_file(candidate)
        except (OSError, ValueError) as exc:
            import logging

            logging.warning("Failed to read Arr keys from %s: %s", candidate, exc)
    return {}


@lru_cache(maxsize=8)
def _parse_keys_file(keys_file: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        keys_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(
                f"Invalid keys line {line_number} in {keys_file}: expected key=value"
            )
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("'").strip('"')
        if name == "" or value == "":
            raise ValueError(
                f"Invalid keys line {line_number} in {keys_file}: empty name or value"
            )
        keys[name] = value
    return keys


def _first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def art_url_for_cache_key(
    cache_key: str,
    *,
    version: int | str | None = None,
) -> str:
    """Build a relative Converter art URL for a cache key.

    Args:
        cache_key: Stable cover-art cache key.
        version: Optional cache-buster (typically ``updated_at`` unix time).

    Returns:
        Relative URL like ``art/film%3A1917%3A2019?v=…``.
    """
    from urllib.parse import quote

    url = f"art/{quote(cache_key, safe='')}"
    if version is None or version == "":
        return url
    return f"{url}?v={version}"


def local_filename_for_cache_key(cache_key: str, extension: str = ".jpg") -> str:
    """Sanitize a cache key into a filesystem-safe poster filename.

    Args:
        cache_key: Cover-art cache key.
        extension: File extension including the leading dot.

    Returns:
        Filename safe for the local cache directory.
    """
    safe = cache_key.replace(":", "_").replace("/", "_")
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"{safe}{extension}"
