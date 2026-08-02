# Architecture

Shared contract: MongoDB collection `media.cover_art_cache`.

```text
Walker / website3
      │
      ▼
 media_cover_art (identity → Arr/TMDB → cache)
      │
      ▼
 cover_art_cache (cache_key, status, remote_url, local_path?, …)
```

- **`remote_url`** is the cross-host value (Walker prefetch + push notifications).
- **`local_path`** is optional and host-specific (website FastAPI disk cache).

Full resolve/hydrate flow is implemented in Phase 1+.
