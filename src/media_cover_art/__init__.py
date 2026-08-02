"""Resolve and cache film/TV cover art from Radarr, Sonarr, and TMDB."""

from __future__ import annotations

from .async_api import (
    ensure_posters as ensure_posters_async,
)
from .async_api import (
    purge_expired as purge_expired_async,
)
from .async_api import (
    refresh_art_for_path,
    resolve_art_for_display,
    resolve_art_for_display_many,
)
from .client import CoverArtClient
from .config import (
    DEFAULT_PLACEHOLDER_ART_URL,
    CoverArtSettings,
    art_url_for_cache_key,
    local_filename_for_cache_key,
)
from .identity import (
    MediaIdentity,
    MediaKind,
    cache_key_for_path,
    normalize_title,
    parse_media_identity,
)
from .models import ArtDisplayFields, ArtProvider, ArtStatus, CoverArtCacheRecord
from .title_match import (
    fold_title_for_match,
    pick_best_item_by_title,
    rank_title_match,
    titles_match_exact,
)

PLACEHOLDER_ART_URL = DEFAULT_PLACEHOLDER_ART_URL

__all__ = [
    "PLACEHOLDER_ART_URL",
    "ArtDisplayFields",
    "ArtProvider",
    "ArtStatus",
    "CoverArtCacheRecord",
    "CoverArtClient",
    "CoverArtSettings",
    "MediaIdentity",
    "MediaKind",
    "art_url_for_cache_key",
    "cache_key_for_path",
    "ensure_posters_async",
    "fold_title_for_match",
    "local_filename_for_cache_key",
    "normalize_title",
    "parse_media_identity",
    "pick_best_item_by_title",
    "purge_expired_async",
    "rank_title_match",
    "refresh_art_for_path",
    "resolve_art_for_display",
    "resolve_art_for_display_many",
    "titles_match_exact",
]

__version__ = "0.1.0"
