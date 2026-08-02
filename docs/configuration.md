# Configuration

Runtime settings come from :class:`~media_cover_art.CoverArtSettings`.

## Environment variables

| Variable | Alias | Purpose |
| -------- | ----- | ------- |
| `MEDIA_COVER_ART_MONGO_URI` | `DB_URL` | Mongo connection URI |
| `MEDIA_COVER_ART_MONGO_DB` | `DB_NAME` | Database (default `media`) |
| `MEDIA_COVER_ART_MONGO_COLLECTION` | — | Collection (default `cover_art_cache`) |
| `MEDIA_COVER_ART_CACHE_DIR` | `CONVERTER_ART_CACHE_DIR` | Local poster dir; omit for metadata-only |
| `MEDIA_COVER_ART_PLACEHOLDER_URL` | — | Placeholder image URL for UI |
| `SONARR_URL` / `RADARR_URL` | — | Arr base URLs |
| `SONARR_API_KEY` / `RADARR_API_KEY` | keys file | Arr API keys |
| `TMDB_API_KEY` | keys file `tmdb_key` | TMDB fallback |

## Keys file

Optional `key=value` file (first existing wins):

1. Path passed to `CoverArtSettings.from_env(keys_file=…)`
2. `/run/secrets/arr-keys.txt`
3. `/app/secrets/arr-keys.txt`

Expected keys: `sonarr_key`, `radarr_key`, optional `tmdb_key` / `tmdb_api_key`.

## Hybrid hosts

| Host | `cache_dir` | Behaviour |
| ---- | ----------- | --------- |
| Walker (NAS) | unset | Writes Mongo `ready` + `remote_url` only |
| website3 FastAPI | `/var/cache/converter-art` | Hydrates local bytes; serves `art/{key}` |
| Converter push | unset | Reads `remote_url` for notification images |

```python
from media_cover_art import CoverArtSettings

settings = CoverArtSettings.from_env()  # Walker: no cache dir
```
