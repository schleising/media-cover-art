# Walker usage

After new media is upserted, call :meth:`~media_cover_art.CoverArtClient.ensure_posters`.

```python
from media_cover_art import CoverArtClient, CoverArtSettings

settings = CoverArtSettings.from_env()  # metadata-only when cache_dir unset
client = CoverArtClient(settings, collection=cover_art_cache_collection)

# Prefer a background thread so the folder walk stays fast
client.ensure_posters(new_filenames)
```

Notes:

- Dedupes by `cache_key` (many episodes → one series poster).
- Soft-fails per title; discovery must not abort on Arr errors.
- Unknown paths (not under `Films`/`TV`) are skipped.
