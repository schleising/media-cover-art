"""Mongo models for the shared cover-art cache."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ArtProvider = Literal["radarr", "sonarr", "tmdb", "none"]
ArtStatus = Literal["ready", "missing", "error", "pending"]


class CoverArtCacheRecord(BaseModel):
    """Document shape for ``media.cover_art_cache``.

    Attributes:
        cache_key: Unique key (for example ``film:1917:2019``).
        kind: Media kind from path identity.
        provider: Which service supplied the poster.
        provider_id: Arr/TMDB id when known.
        remote_url: Public HTTPS poster URL (cross-host contract).
        local_path: Optional host-local cached file path.
        status: Resolution state.
        matched_title: Provider title chosen by Policy C.
        last_attempt_at: Last resolve attempt timestamp.
        last_accessed_at: Last serve/access timestamp (retention).
        updated_at: Last write timestamp.
        content_type: Image content type when bytes were stored.
        error_detail: Optional error text for ``error`` status.
    """

    cache_key: str
    kind: Literal["film", "tv", "unknown"]
    provider: ArtProvider = "none"
    provider_id: str | None = None
    remote_url: str | None = None
    local_path: str | None = None
    status: ArtStatus = "pending"
    matched_title: str | None = None
    last_attempt_at: datetime | None = None
    last_accessed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_type: str | None = None
    error_detail: str | None = None


class ArtDisplayFields(BaseModel):
    """Fields for UI / websocket rows that show cover art.

    Attributes:
        filename: Basename (or caller-chosen label key).
        display_title: Human-readable title from identity.
        media_kind: ``film``, ``tv``, or ``unknown``.
        cover_art_url: Relative or absolute URL for the poster/placeholder.
        cache_key: Matching cache document key.
        cover_art_status: Cache status string for the UI.
    """

    filename: str
    display_title: str
    media_kind: Literal["film", "tv", "unknown"]
    cover_art_url: str
    cache_key: str
    cover_art_status: str = "pending"
