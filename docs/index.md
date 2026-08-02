# Media Cover Art

Resolve and cache film/TV **cover art** for library paths under `Films` and `TV`, using Radarr/Sonarr first and TMDB as fallback.

## Install

```bash
pip install "media-cover-art @ git+https://github.com/schleising/media-cover-art.git@v0.1.0"
```

## Quick start

```python
from media_cover_art import CoverArtClient, CoverArtSettings, parse_media_identity

identity = parse_media_identity(
    "/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"
)

with CoverArtClient(CoverArtSettings.from_env()) as client:
    client.ensure_posters([identity.source_path])
    record = client.get_ready_record(identity.source_path)
```

See [Install](install.md), [Configuration](configuration.md), and the [API reference](api.md).

Published docs: [https://schleising.github.io/media-cover-art/](https://schleising.github.io/media-cover-art/)
