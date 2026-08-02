"""Parse media paths into stable film/TV identities for cover art."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote

MediaKind = Literal["film", "tv", "unknown"]

QUALITY_TOKENS = re.compile(
    r"\b(bluray|blu-ray|webdl|web-dl|webrip|hdtv|remux|x264|x265|h264|h265|"
    r"hevc|aac|dts|truehd|atmos|hdr|dv|2160p|1080p|720p|480p|proper|repack)\b",
    re.IGNORECASE,
)
YEAR_IN_PARENS = re.compile(r"^(?P<title>.+?)\s*\((?P<year>19\d{2}|20\d{2})\)$")
YEAR_AT_END = re.compile(r"^(?P<title>.+?)\s+(?P<year>19\d{2}|20\d{2})$")
SEASON_FOLDER = re.compile(r"^Season\s+(?P<season>\d+)$", re.IGNORECASE)
EPISODE_TAG = re.compile(
    r"(?P<prefix>.*?)(?:\s*-\s*)?S(?P<season>\d{1,2})E(?P<episode>\d{1,3})"
    r"(?:\s*-\s*(?P<title>.+))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MediaIdentity:
    """Stable identity derived from a full media filesystem path.

    Attributes:
        kind: Whether the path is a film, TV episode/show, or unknown.
        title: Film title or TV show name.
        source_path: Original full path used for parsing.
        display_title: Human-readable label for UI rows.
        cache_key: Stable key for the cover-art cache collection.
        year: Release year when known (films).
        season: Season number when known (TV).
        episode: Episode number when known (TV).
        episode_title: Episode title when parsed from the basename.
    """

    kind: MediaKind
    title: str
    source_path: str
    display_title: str
    cache_key: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None


def normalize_title(value: str) -> str:
    """Lowercase a title and strip quality tokens / punctuation noise.

    Args:
        value: Raw title, folder name, or basename fragment.

    Returns:
        Normalized lowercase string suitable for slug or match prep.
    """
    cleaned = QUALITY_TOKENS.sub(" ", value)
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _slug_for_cache(value: str) -> str:
    slug = normalize_title(value)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "unknown"


def _strip_quality_and_ext(name: str) -> str:
    stem = Path(name).stem
    cleaned = QUALITY_TOKENS.sub(" ", stem)
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _parse_title_year(folder_or_name: str) -> tuple[str, int | None]:
    text = folder_or_name.strip()
    year_match = YEAR_IN_PARENS.match(text)
    if year_match is not None:
        return year_match.group("title").strip(), int(year_match.group("year"))

    year_match = YEAR_AT_END.match(text)
    if year_match is not None:
        return year_match.group("title").strip(), int(year_match.group("year"))

    return text, None


def _path_parts(source_path: str) -> list[str]:
    normalized = unquote(source_path.replace("\\", "/")).strip("/")
    return [part for part in normalized.split("/") if part]


def parse_media_identity(source_path: str) -> MediaIdentity:
    """Derive film/TV identity from a full media path.

    Paths under ``Films`` / ``TV`` (case-insensitive path segments) produce
    film or TV identities. Anything else is ``unknown`` and will not trigger
    remote cover-art lookups.

    Args:
        source_path: Full POSIX (or Windows) path as stored in Mongo.

    Returns:
        A ``MediaIdentity`` including ``cache_key`` and ``display_title``.
    """
    parts = _path_parts(source_path)
    lowered = [part.lower() for part in parts]

    if "films" in lowered:
        return _parse_film(source_path, parts, lowered.index("films"))
    if "tv" in lowered:
        return _parse_tv(source_path, parts, lowered.index("tv"))

    basename = Path(source_path).name
    return MediaIdentity(
        kind="unknown",
        title=Path(basename).stem or basename,
        source_path=source_path,
        display_title=basename,
        cache_key=f"unknown:{_slug_for_cache(basename)}",
    )


def cache_key_for_path(source_path: str) -> str:
    """Return the cover-art cache key for a media path.

    Args:
        source_path: Full media path.

    Returns:
        The ``cache_key`` from ``parse_media_identity``.
    """
    return parse_media_identity(source_path).cache_key


def _parse_film(source_path: str, parts: list[str], films_index: int) -> MediaIdentity:
    basename = parts[-1] if parts else Path(source_path).name
    folder: str | None = None
    if films_index + 1 < len(parts) - 1:
        folder = parts[films_index + 1]

    if folder:
        title, year = _parse_title_year(folder)
    else:
        title, year = _parse_title_year(_strip_quality_and_ext(basename))

    display = f"{title} ({year})" if year is not None else title
    cache_key = f"film:{_slug_for_cache(title)}"
    if year is not None:
        cache_key = f"{cache_key}:{year}"

    return MediaIdentity(
        kind="film",
        title=title,
        year=year,
        source_path=source_path,
        display_title=display,
        cache_key=cache_key,
    )


def _parse_tv(source_path: str, parts: list[str], tv_index: int) -> MediaIdentity:
    basename = parts[-1] if parts else Path(source_path).name
    show = "Unknown Show"
    if tv_index + 1 < len(parts):
        show = parts[tv_index + 1]

    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None

    for part in parts[tv_index + 2 :]:
        season_match = SEASON_FOLDER.match(part)
        if season_match is not None:
            season = int(season_match.group("season"))
            break

    episode_match = EPISODE_TAG.search(_strip_quality_and_ext(basename))
    if episode_match is not None:
        season = int(episode_match.group("season"))
        episode = int(episode_match.group("episode"))
        raw_title = episode_match.group("title")
        if raw_title:
            episode_title = QUALITY_TOKENS.sub(" ", raw_title).strip(" -")
            episode_title = re.sub(r"\s+", " ", episode_title).strip() or None

    if season is not None and episode is not None:
        display = f"{show} · S{season:02d}E{episode:02d}"
        if episode_title:
            display = f"{display} · {episode_title}"
    elif season is not None:
        display = f"{show} · Season {season}"
    else:
        display = show

    return MediaIdentity(
        kind="tv",
        title=show,
        season=season,
        episode=episode,
        episode_title=episode_title,
        source_path=source_path,
        display_title=display,
        cache_key=f"tvshow:{_slug_for_cache(show)}",
    )
