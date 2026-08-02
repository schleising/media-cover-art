# Media Cover Art

Resolve and cache film/TV **cover art** for library paths under `Films` and `TV`, using Radarr/Sonarr first and TMDB as fallback.

## Status

**Phase 0** — identity parsing, Policy C title matching, and cache models are available now. The sync client (`CoverArtClient.ensure_posters`, resolve, hydrate, purge) lands in Phase 1.

## Quick start

```python
from media_cover_art import parse_media_identity

identity = parse_media_identity(
    "/Media/TV/100 Foot Wave/Season 1/"
    "100 Foot Wave - S01E01 - Chapter I – Sea Monsters WEBDL-1080p.mkv"
)
print(identity.cache_key)      # tvshow:100-foot-wave
print(identity.display_title)  # 100 Foot Wave · S01E01 · Chapter I – Sea Monsters
```

See [Install](install.md) and the [API reference](api.md).
