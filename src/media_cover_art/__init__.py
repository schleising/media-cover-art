"""Resolve and cache film/TV cover art from Radarr, Sonarr, and TMDB.

Phase 0 exports identity parsing, title matching, and cache models.
The sync client (ensure/resolve/purge) lands in a later phase.
"""

from __future__ import annotations

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

__all__ = [
    "ArtDisplayFields",
    "ArtProvider",
    "ArtStatus",
    "CoverArtCacheRecord",
    "MediaIdentity",
    "MediaKind",
    "cache_key_for_path",
    "fold_title_for_match",
    "normalize_title",
    "parse_media_identity",
    "pick_best_item_by_title",
    "rank_title_match",
    "titles_match_exact",
]

__version__ = "0.1.0.dev0"
