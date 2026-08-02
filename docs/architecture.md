# Architecture

```text
Walker / website3 / converter push
              │
              ▼
     media_cover_art.CoverArtClient
              │
     ┌────────┴────────┐
     ▼                 ▼
 Arr (Radarr/Sonarr)  TMDB
     │                 │
     └────────┬────────┘
              ▼
   MongoDB media.cover_art_cache
   (cache_key, status, remote_url, local_path?, …)
              │
              ▼
   optional host-local cache_dir bytes
```

## Resolve order

1. Parse path → identity / `cache_key`
2. Honor negative-cache TTLs (`missing` 7d, `error` 2m)
3. Film: Radarr library → lookup → TMDB
4. TV: Sonarr series poster → lookup → TMDB
5. Persist `ready` with `remote_url`; write local bytes only if `cache_dir` set

## Hydrate

`status=ready` + `remote_url` + missing local file + `cache_dir` set → download `remote_url` into cache without Arr re-query.
