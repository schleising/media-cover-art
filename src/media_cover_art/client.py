"""Sync cover-art client: resolve, ensure, hydrate, purge."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from pymongo.collection import Collection
from pymongo.database import Database

from .arr_client import ArrClient
from .cache import CoverArtCache, open_collection
from .config import CoverArtSettings
from .identity import MediaIdentity, parse_media_identity
from .models import ArtDisplayFields, ArtProvider, CoverArtCacheRecord
from .tmdb_client import TmdbClient

logger = logging.getLogger("media_cover_art.client")


class CoverArtClient:
    """Sync cover-art resolver shared by Walker, website3, and push consumers.

    Args:
        settings: Runtime configuration.
        collection: Optional injected pymongo collection (tests / shared client).
        database: Optional injected database (collection derived from settings).
        http_client: Optional shared ``httpx.Client``.
    """

    def __init__(
        self,
        settings: CoverArtSettings,
        *,
        collection: Collection[dict[str, Any]] | None = None,
        database: Database[dict[str, Any]] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._owns_http = http_client is None
        timeout = httpx.Timeout(
            connect=settings.connect_timeout_seconds,
            read=settings.read_timeout_seconds,
            write=settings.read_timeout_seconds,
            pool=settings.connect_timeout_seconds,
        )
        self._http = http_client or httpx.Client(
            timeout=timeout, follow_redirects=True
        )
        resolved = collection or open_collection(settings, database=database)
        self._cache = CoverArtCache(settings, resolved)
        self._arr = ArrClient(settings, self._http)
        self._tmdb = TmdbClient(settings, self._http)
        self._indexes_ready = False
        self._errors_cleared = False

    def close(self) -> None:
        """Close the owned HTTP client, if any."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> CoverArtClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def cache(self) -> CoverArtCache:
        return self._cache

    def ensure_indexes(self) -> None:
        """Create Mongo indexes (idempotent)."""
        self._cache.ensure_indexes()
        self._indexes_ready = True

    def clear_errors(self) -> int:
        """Clear ``error`` cache rows so they can be retried."""
        deleted = self._cache.clear_error_cache_records()
        self._errors_cleared = True
        return deleted

    def purge_expired(self) -> dict[str, int]:
        """Purge unused ready posters past retention."""
        self._ensure_runtime()
        return self._cache.purge_expired()

    def get_ready_record(self, source_path: str) -> CoverArtCacheRecord | None:
        """Return a ready cache row for ``source_path``, if present.

        Args:
            source_path: Full media path.

        Returns:
            Ready ``CoverArtCacheRecord``, or ``None``.
        """
        identity = parse_media_identity(source_path)
        record = self._cache.get_cache_record(identity.cache_key)
        if record is None or record.status != "ready":
            return None
        return record

    def ensure_posters(self, source_paths: list[str]) -> list[CoverArtCacheRecord]:
        """Resolve posters for paths (Walker prefetch). Soft-fails per title.

        Dedupes by ``cache_key``. Skips unknown kinds and fresh negatives.
        Writes local bytes only when ``settings.cache_dir`` is set.

        Args:
            source_paths: Full media paths newly discovered.

        Returns:
            Cache records for the unique keys that were considered.
        """
        self._ensure_runtime()
        identities_by_key: dict[str, MediaIdentity] = {}
        for path in source_paths:
            identity = parse_media_identity(path)
            if identity.kind == "unknown":
                continue
            identities_by_key.setdefault(identity.cache_key, identity)

        results: list[CoverArtCacheRecord] = []
        existing = self._cache.get_cache_records(list(identities_by_key))
        for cache_key, identity in identities_by_key.items():
            record = existing.get(cache_key)
            try:
                if not self._cache.should_resolve(identity, record):
                    if record is not None:
                        results.append(record)
                    continue
                resolved = self._resolve_one(identity)
                results.append(resolved)
            except Exception as exc:  # noqa: BLE001 — Walker must not fail discovery
                logger.exception(
                    "ensure_posters failed for %s: %s", identity.cache_key, exc
                )
                error_record = self._cache.mark_status(
                    identity,
                    "error",
                    error_detail=f"{type(exc).__name__}: {exc}",
                )
                self._cache.upsert_cache_record(error_record)
                results.append(error_record)
        return results

    def resolve_for_display(self, source_path: str) -> ArtDisplayFields:
        """Resolve display fields for one path (may hydrate / enqueue resolve)."""
        return self.resolve_for_display_many([source_path])[0]

    def peek_for_display_many(
        self, source_paths: list[str]
    ) -> tuple[list[ArtDisplayFields], list[str]]:
        """Return display fields without blocking on Arr/TMDB.

        Also returns source paths that still need hydrate or full resolve so
        callers (e.g. website3 websocket) can enqueue background work.

        Args:
            source_paths: Full media paths.

        Returns:
            ``(display_fields, paths_needing_work)``.
        """
        self._ensure_runtime()
        identities = [parse_media_identity(path) for path in source_paths]
        records = self._cache.get_cache_records([i.cache_key for i in identities])
        fields: list[ArtDisplayFields] = []
        needs_work: list[str] = []
        seen_keys: set[str] = set()
        for identity in identities:
            record = records.get(identity.cache_key)
            fields.append(self._cache.display_fields_for(identity, record))
            if identity.kind == "unknown":
                continue
            if identity.cache_key in seen_keys:
                continue
            if self._cache.needs_hydrate(record) or self._cache.should_resolve(
                identity, record
            ):
                seen_keys.add(identity.cache_key)
                needs_work.append(identity.source_path)
        return fields, needs_work

    def resolve_for_display_many(
        self, source_paths: list[str]
    ) -> list[ArtDisplayFields]:
        """Resolve display fields for many paths.

        Hydrates local files when ready+``remote_url`` and ``cache_dir`` is set.
        Runs full resolve inline for cold keys (callers that need non-blocking
        behaviour should use :meth:`peek_for_display_many` plus a background
        queue).

        Args:
            source_paths: Full media paths.

        Returns:
            Parallel list of ``ArtDisplayFields``.
        """
        self._ensure_runtime()
        identities = [parse_media_identity(path) for path in source_paths]
        records = self._cache.get_cache_records([i.cache_key for i in identities])
        fields: list[ArtDisplayFields] = []
        for identity in identities:
            record = records.get(identity.cache_key)
            try:
                if self._cache.needs_hydrate(record) and record is not None:
                    record = self._hydrate(identity, record)
                    records[identity.cache_key] = record
                elif self._cache.should_resolve(identity, record):
                    record = self._resolve_one(identity)
                    records[identity.cache_key] = record
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "resolve_for_display failed for %s: %s", identity.cache_key, exc
                )
                error_record = self._cache.mark_status(
                    identity,
                    "error",
                    error_detail=f"{type(exc).__name__}: {exc}",
                )
                self._cache.upsert_cache_record(error_record)
                record = error_record
                records[identity.cache_key] = record
            fields.append(self._cache.display_fields_for(identity, record))
        return fields

    def refresh(self, source_path: str) -> ArtDisplayFields:
        """Force re-resolve for a path, ignoring negative-cache TTLs."""
        self._ensure_runtime()
        identity = parse_media_identity(source_path)
        record = self._resolve_one(identity, force=True)
        return self._cache.display_fields_for(identity, record)

    def get_local_poster_path(self, cache_key: str) -> Path | None:
        """Return the local poster path for a cache key if the file exists."""
        record = self._cache.get_cache_record(cache_key)
        if record is None:
            return None
        return self._cache.resolve_local_path(record)

    def touch_access(self, cache_key: str) -> None:
        """Refresh last-accessed timestamp for retention."""
        self._cache.touch_cache_access(cache_key)

    def _ensure_runtime(self) -> None:
        if self.settings.cache_dir is not None:
            self._cache.ensure_cache_dir()
        if not self._indexes_ready:
            try:
                self.ensure_indexes()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed creating cover art indexes: %s", exc)
                self._indexes_ready = True
        if not self._errors_cleared:
            try:
                self.clear_errors()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed clearing error cache records: %s", exc)
                self._errors_cleared = True

    def _hydrate(
        self,
        identity: MediaIdentity,
        record: CoverArtCacheRecord,
    ) -> CoverArtCacheRecord:
        assert record.remote_url is not None
        data, content_type = self._download_remote(record.remote_url, record.provider)
        local_path, resolved_type = self._cache.write_poster_bytes(
            identity.cache_key, data, content_type
        )
        updated = self._cache.mark_status(
            identity,
            "ready",
            provider=record.provider,
            provider_id=record.provider_id,
            remote_url=record.remote_url,
            local_path=local_path,
            content_type=resolved_type,
            matched_title=record.matched_title,
        )
        self._cache.upsert_cache_record(updated)
        return updated

    def _resolve_one(
        self,
        identity: MediaIdentity,
        *,
        force: bool = False,
    ) -> CoverArtCacheRecord:
        existing = self._cache.get_cache_record(identity.cache_key)
        if not force and existing is not None:
            if (
                existing.status == "ready"
                and existing.local_path
                and Path(existing.local_path).is_file()
            ):
                return existing
            if self._cache.needs_hydrate(existing):
                return self._hydrate(identity, existing)
            if not self._cache.should_resolve(identity, existing):
                return existing

        arr_result = self._arr.lookup_poster(identity)
        if arr_result is not None:
            return self._persist_ready(
                identity,
                provider=arr_result.provider,
                provider_id=arr_result.provider_id,
                remote_url=arr_result.remote_url,
                matched_title=arr_result.matched_title,
                download_api_key=arr_result.api_key if arr_result.use_api_key else None,
            )

        tmdb_result = self._tmdb.lookup_poster(identity)
        if tmdb_result is not None:
            return self._persist_ready(
                identity,
                provider="tmdb",
                provider_id=tmdb_result.provider_id,
                remote_url=tmdb_result.remote_url,
                matched_title=tmdb_result.matched_title,
            )

        missing = self._cache.mark_status(identity, "missing")
        self._cache.upsert_cache_record(missing)
        return missing

    def _persist_ready(
        self,
        identity: MediaIdentity,
        *,
        provider: ArtProvider,
        provider_id: str | None,
        remote_url: str,
        matched_title: str | None,
        download_api_key: str | None = None,
    ) -> CoverArtCacheRecord:
        local_path: str | None = None
        content_type: str | None = None
        if self.settings.cache_dir is not None:
            data, content_type = self._download_remote(
                remote_url, provider, api_key=download_api_key
            )
            local_path, content_type = self._cache.write_poster_bytes(
                identity.cache_key, data, content_type
            )
        record = self._cache.mark_status(
            identity,
            "ready",
            provider=provider,
            provider_id=provider_id,
            remote_url=remote_url,
            local_path=local_path,
            content_type=content_type,
            matched_title=matched_title,
        )
        self._cache.upsert_cache_record(record)
        return record

    def _download_remote(
        self,
        url: str,
        provider: str,
        *,
        api_key: str | None = None,
    ) -> tuple[bytes, str | None]:
        if provider == "tmdb":
            return self._tmdb.download_image(url)
        return self._arr.download_image(url, api_key=api_key)
