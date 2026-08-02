# Configuration

!!! note "Phase 1"
    `CoverArtSettings` and env loading land in Phase 1. This page will document Arr/TMDB keys, Mongo URI, cache directory, and TTLs.

Planned settings (design):

| Setting | Role |
| ------- | ---- |
| Sonarr / Radarr URL + API key | Primary poster source |
| TMDB API key | Fallback search |
| Mongo URI / DB / collection | Shared `cover_art_cache` |
| `cache_dir` | Optional host-local poster bytes (`None` = metadata-only) |
