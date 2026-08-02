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
pip install "media-cover-art @ git+https://github.com/schleising/media-cover-art.git@v0.1.0"
```

Editable (local sibling checkout):

```bash
pip install -e /Users/steve/Documents/Coding/Python/media-cover-art
```

With docs extras:

```bash
pip install -e ".[docs,dev]"
```

## Quick start

```python
from media_cover_art import CoverArtClient, CoverArtSettings, parse_media_identity

identity = parse_media_identity(
    "/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"
)
assert identity.cache_key == "film:1917:2019"

with CoverArtClient(CoverArtSettings.from_env()) as client:
    client.ensure_posters([identity.source_path])
```

## Documentation

- Published: https://schleising.github.io/media-cover-art/
- Local: `pip install -e ".[docs]" && mkdocs serve`

## Development

```bash
pip install -e ".[dev,docs]"
pytest
basedpyright
mkdocs build --strict
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
