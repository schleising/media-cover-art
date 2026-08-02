# Changelog

## 0.1.1

- Fix `CoverArtClient` init: compare injected pymongo collections with `is not None` (collections are not truthy)

## 0.1.0

- Sync `CoverArtClient` with Arr → TMDB resolve, Mongo cache, optional disk
- `ensure_posters` (Walker prefetch), hydrate-on-miss, purge, async helpers
- MkDocs Material docs on GitHub Pages
- Identity parsing + Policy C title matching

## 0.1.0.dev0 (Phase 0)

- Package skeleton, identity/title_match/models, CI, docs scaffold
