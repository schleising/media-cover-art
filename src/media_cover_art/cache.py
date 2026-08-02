"""Sync Mongo + filesystem cover-art cache helpers."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pymongo.collection import Collection
from pymongo.database import Database

from .config import (
    CoverArtSettings,
    art_url_for_cache_key,
    local_filename_for_cache_key,
)
from .identity import MediaIdentity
from .models import ArtDisplayFields, ArtProvider, ArtStatus, CoverArtCacheRecord

logger = logging.getLogger("media_cover_art.cache")


class CoverArtCache:
    """Sync cover-art cache over a pymongo collection and optional disk dir."""

    def __init__(
        self,
        settings: CoverArtSettings,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._settings = settings
        self._collection = collection

    @property
    def collection(self) -> Collection[dict[str, Any]]:
        return self._collection

    def ensure_cache_dir(self) -> Path | None:
        """Create the local cache directory when configured."""
        directory = self._settings.cache_dir
        if directory is None:
            return None
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Cannot create cover art cache dir %s: %s", directory, exc)
        return directory

    def clear_error_cache_records(self) -> int:
        """Delete ``error`` rows so resolution can retry after a fix/redeploy."""
        result = self._collection.delete_many({"status": "error"})
        deleted = int(result.deleted_count)
        if deleted:
            logger.info("Cleared %s cover art error cache records for retry", deleted)
        return deleted

    def ensure_indexes(self) -> None:
        """Create unique ``cache_key`` and retention helper indexes."""
        _ = self._collection.create_index("cache_key", unique=True)
        _ = self._collection.create_index("updated_at")
        _ = self._collection.create_index("last_accessed_at")

    def touch_cache_access(self, cache_key: str) -> None:
        """Refresh ``last_accessed_at`` for retention."""
        if not cache_key:
            return
        _ = self._collection.update_one(
            {"cache_key": cache_key},
            {"$set": {"last_accessed_at": datetime.now(UTC)}},
        )

    def purge_expired(self) -> dict[str, int]:
        """Delete cache rows and poster files unused longer than retention."""
        deleted_records = 0
        deleted_files = 0
        orphan_files = 0
        retention = self._settings.ready_retention_seconds
        cutoff = datetime.now(UTC) - timedelta(seconds=retention)

        query = {
            "$or": [
                {"last_accessed_at": {"$lt": cutoff}},
                {
                    "last_accessed_at": {"$in": [None]},
                    "updated_at": {"$lt": cutoff},
                },
                {
                    "last_accessed_at": {"$exists": False},
                    "updated_at": {"$lt": cutoff},
                },
            ]
        }
        documents = list(self._collection.find(query).limit(10_000))
        for document in documents:
            record = _as_record(cast(Mapping[str, object], document))
            if record is None:
                continue
            if _delete_local_poster(record.local_path):
                deleted_files += 1
            result = self._collection.delete_one({"cache_key": record.cache_key})
            deleted_records += int(result.deleted_count)

        kept_paths: set[str] = set()
        for document in self._collection.find(
            {"local_path": {"$type": "string"}},
            {"local_path": 1},
        ).limit(50_000):
            local_path = document.get("local_path")
            if isinstance(local_path, str) and local_path:
                kept_paths.add(local_path)

        cache_dir = self._settings.cache_dir
        if cache_dir is not None and cache_dir.is_dir():
            cutoff_mtime = cutoff.timestamp()
            for path in cache_dir.iterdir():
                if not path.is_file():
                    continue
                try:
                    if path.stat().st_mtime >= cutoff_mtime:
                        continue
                except OSError:
                    continue
                if str(path) in kept_paths:
                    continue
                if _delete_local_poster(str(path)):
                    orphan_files += 1

        if deleted_records or deleted_files or orphan_files:
            logger.info(
                "Purged cover art older than %s days: records=%s files=%s orphans=%s",
                retention // (24 * 60 * 60),
                deleted_records,
                deleted_files,
                orphan_files,
            )
        return {
            "deleted_records": deleted_records,
            "deleted_files": deleted_files,
            "orphan_files": orphan_files,
        }

    def get_cache_record(self, cache_key: str) -> CoverArtCacheRecord | None:
        document = self._collection.find_one({"cache_key": cache_key})
        return _as_record(cast(Mapping[str, object] | None, document))

    def get_cache_records(
        self, cache_keys: list[str]
    ) -> dict[str, CoverArtCacheRecord]:
        if not cache_keys:
            return {}
        unique_keys = list(dict.fromkeys(cache_keys))
        documents = list(
            self._collection.find({"cache_key": {"$in": unique_keys}}).limit(
                len(unique_keys)
            )
        )
        records: dict[str, CoverArtCacheRecord] = {}
        for document in documents:
            record = _as_record(cast(Mapping[str, object], document))
            if record is not None:
                records[record.cache_key] = record
        return records

    def upsert_cache_record(self, record: CoverArtCacheRecord) -> None:
        payload = record.model_dump()
        result = self._collection.update_one(
            {"cache_key": record.cache_key},
            {"$set": payload},
            upsert=True,
        )
        logger.debug(
            "upsert %s status=%s provider=%s matched=%s modified=%s upserted=%s local=%s",
            record.cache_key,
            record.status,
            record.provider,
            result.matched_count,
            result.modified_count,
            result.upserted_id is not None,
            record.local_path,
        )

    def write_poster_bytes(
        self,
        cache_key: str,
        data: bytes,
        content_type: str | None,
    ) -> tuple[str, str]:
        """Write poster bytes when ``cache_dir`` is set.

        Returns:
            ``(local_path, content_type)``.

        Raises:
            RuntimeError: If no cache directory is configured.
            OSError: On write failure.
        """
        cache_dir = self.ensure_cache_dir()
        if cache_dir is None:
            raise RuntimeError("cache_dir is not configured; cannot write poster bytes")

        extension = ".jpg"
        resolved_type = (content_type or "image/jpeg").split(";")[0].strip().lower()
        if resolved_type == "image/png":
            extension = ".png"
        elif resolved_type == "image/webp":
            extension = ".webp"
        elif resolved_type not in {"image/jpeg", "image/jpg"}:
            resolved_type = "image/jpeg"
            extension = ".jpg"

        filename = local_filename_for_cache_key(cache_key, extension)
        path = cache_dir / filename
        _ = path.write_bytes(data)
        logger.debug(
            "Wrote poster %s (%s bytes, %s) writable_dir=%s",
            path,
            len(data),
            resolved_type,
            os.access(cache_dir, os.W_OK),
        )
        return str(path), resolved_type

    def resolve_local_path(self, record: CoverArtCacheRecord) -> Path | None:
        if not record.local_path:
            return None
        path = Path(record.local_path)
        if path.is_file():
            return path
        return None

    def record_is_fresh_negative(self, record: CoverArtCacheRecord) -> bool:
        if record.last_attempt_at is None:
            return False
        age = datetime.now(UTC) - _as_utc(record.last_attempt_at)
        if record.status == "missing":
            return age < timedelta(seconds=self._settings.missing_ttl_seconds)
        if record.status == "error":
            return age < timedelta(seconds=self._settings.error_ttl_seconds)
        return False

    def should_resolve(
        self, identity: MediaIdentity, record: CoverArtCacheRecord | None
    ) -> bool:
        """Whether a full Arr/TMDB resolve should run for this identity."""
        if identity.kind == "unknown":
            return False
        if record is None:
            return True
        if record.status == "ready":
            if record.local_path and Path(record.local_path).is_file():
                return False
            # ready with remote_url only: hydrate if cache_dir set, else done
            if self._settings.cache_dir is None and record.remote_url:
                return False
            if record.remote_url:
                return False  # hydrate path handles this
            return True
        if record.status in {"missing", "error"} and self.record_is_fresh_negative(
            record
        ):
            return False
        return True

    def needs_hydrate(self, record: CoverArtCacheRecord | None) -> bool:
        """True when ready+remote_url but local file missing and cache_dir set."""
        if self._settings.cache_dir is None or record is None:
            return False
        if record.status != "ready" or not record.remote_url:
            return False
        if record.local_path and Path(record.local_path).is_file():
            return False
        return True

    def display_fields_for(
        self,
        identity: MediaIdentity,
        record: CoverArtCacheRecord | None,
    ) -> ArtDisplayFields:
        """Build UI display fields for a path identity + cache row."""
        basename = Path(identity.source_path).name
        placeholder = self._settings.placeholder_art_url
        if identity.kind == "unknown":
            status = "unknown"
            cover_art_url = placeholder
        elif (
            record is not None
            and record.status == "ready"
            and record.local_path
            and Path(record.local_path).is_file()
        ):
            status = "ready"
            version: int | str | None = None
            if record.updated_at is not None:
                version = int(record.updated_at.timestamp())
            cover_art_url = art_url_for_cache_key(identity.cache_key, version=version)
        elif record is not None and record.status == "ready" and record.local_path:
            status = "ready_missing_file"
            cover_art_url = placeholder
        elif record is not None and record.status == "ready" and record.remote_url:
            # Metadata-ready but not hydrated yet — still pending for local UI.
            status = "pending"
            cover_art_url = placeholder
        elif record is not None:
            status = record.status
            cover_art_url = placeholder
            if record.error_detail:
                status = f"{record.status}:{record.error_detail[:80]}"
        else:
            status = "pending"
            cover_art_url = placeholder

        return ArtDisplayFields(
            filename=basename,
            display_title=identity.display_title,
            media_kind=identity.kind,
            cover_art_url=cover_art_url,
            cache_key=identity.cache_key,
            cover_art_status=status,
        )

    def mark_status(
        self,
        identity: MediaIdentity,
        status: ArtStatus,
        *,
        provider: ArtProvider = "none",
        provider_id: str | None = None,
        remote_url: str | None = None,
        local_path: str | None = None,
        content_type: str | None = None,
        error_detail: str | None = None,
        matched_title: str | None = None,
    ) -> CoverArtCacheRecord:
        now = datetime.now(UTC)
        return CoverArtCacheRecord(
            cache_key=identity.cache_key,
            kind=identity.kind if identity.kind != "unknown" else "unknown",
            provider=provider,
            provider_id=provider_id,
            remote_url=remote_url,
            local_path=local_path,
            status=status,
            matched_title=matched_title,
            last_attempt_at=now,
            last_accessed_at=now if status == "ready" else None,
            updated_at=now,
            content_type=content_type,
            error_detail=error_detail,
        )


def open_collection(
    settings: CoverArtSettings,
    *,
    database: Database[dict[str, Any]] | None = None,
) -> Collection[dict[str, Any]]:
    """Open the cover-art Mongo collection from settings or an injected DB."""
    if database is not None:
        return database[settings.mongo_collection]
    from pymongo import MongoClient

    client: MongoClient[dict[str, Any]] = MongoClient(
        settings.mongo_uri, serverSelectionTimeoutMS=5_000
    )
    return client[settings.mongo_db][settings.mongo_collection]


def _delete_local_poster(local_path: str | None) -> bool:
    if not local_path:
        return False
    path = Path(local_path)
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError as exc:
        logger.warning("Failed deleting cover art file %s: %s", path, exc)
    return False


def _as_record(document: Mapping[str, object] | None) -> CoverArtCacheRecord | None:
    if document is None:
        return None
    payload = {str(key): value for key, value in document.items()}
    payload.pop("_id", None)
    try:
        return CoverArtCacheRecord.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid cover art cache document: %s", exc)
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
