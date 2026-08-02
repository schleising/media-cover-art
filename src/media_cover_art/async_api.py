"""Async helpers that wrap the sync :class:`CoverArtClient`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

from .client import CoverArtClient
from .models import ArtDisplayFields, CoverArtCacheRecord

T = TypeVar("T")


async def _to_thread(func: Callable[..., T], *args: object) -> T:
    return await asyncio.to_thread(func, *args)


async def resolve_art_for_display(
    client: CoverArtClient, source_path: str
) -> ArtDisplayFields:
    """Async wrapper for :meth:`CoverArtClient.resolve_for_display`."""
    return await _to_thread(client.resolve_for_display, source_path)


async def resolve_art_for_display_many(
    client: CoverArtClient, source_paths: list[str]
) -> list[ArtDisplayFields]:
    """Async wrapper for :meth:`CoverArtClient.resolve_for_display_many`."""
    return await _to_thread(client.resolve_for_display_many, source_paths)


async def refresh_art_for_path(
    client: CoverArtClient, source_path: str
) -> ArtDisplayFields:
    """Async wrapper for :meth:`CoverArtClient.refresh`."""
    return await _to_thread(client.refresh, source_path)


async def ensure_posters(
    client: CoverArtClient, source_paths: list[str]
) -> list[CoverArtCacheRecord]:
    """Async wrapper for :meth:`CoverArtClient.ensure_posters`."""
    return await _to_thread(client.ensure_posters, source_paths)


async def purge_expired(client: CoverArtClient) -> dict[str, int]:
    """Async wrapper for :meth:`CoverArtClient.purge_expired`."""
    return await _to_thread(client.purge_expired)
