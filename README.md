# Media Cover Art

Resolve and cache film/TV cover art from Radarr, Sonarr, and TMDB.

This library is shared by:

- **convert-to-h265** Walker — prefetch posters when new media is discovered
- **website3** Converter — display, hydrate local bytes, and serve cached art
- **convert-to-h265** converter — web-push notification images via `remote_url`

Phase 0 ships identity parsing, Policy C title matching, and cache models.
The sync client (`ensure_posters`, resolve, purge) follows in a later phase.

## Install

```bash
pip install "media-cover-art @ git+https://github.com/schleising/media-cover-art.git@main"
```

Editable (local sibling checkout):

```bash
pip install -e /Users/steve/Documents/Coding/Python/media-cover-art
```

With docs extras:

```bash
pip install -e ".[docs,dev]"
```

## Quick start (Phase 0)

```python
from media_cover_art import parse_media_identity, cache_key_for_path

identity = parse_media_identity(
    "/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"
)
assert identity.cache_key == "film:1917:2019"
assert cache_key_for_path(identity.source_path) == identity.cache_key
```

## Documentation

```bash
pip install -e ".[docs]"
mkdocs serve
```

Then open the local MkDocs Material site (default `http://127.0.0.1:8000`).

## Development

```bash
pip install -e ".[dev,docs]"
pytest
basedpyright
mkdocs build --strict
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
