# website3 usage

website3 keeps HTTP serving and a non-blocking websocket queue in-app, and uses this package for resolve/hydrate/purge.

```python
from media_cover_art import CoverArtClient, CoverArtSettings

settings = CoverArtSettings.from_env(keys_file="/run/secrets/arr-keys.txt")
# cache_dir set via CONVERTER_ART_CACHE_DIR / MEDIA_COVER_ART_CACHE_DIR
client = CoverArtClient(settings)

# Hot path: peek cache, enqueue work separately
fields, needs_work = client.peek_for_display_many(paths)

# Worker / thread:
client.resolve_for_display(path)  # hydrate or full Arr→TMDB resolve
```

When Walker has already written `ready` + `remote_url`, website3 **hydrates** poster bytes into the local cache without re-querying Arr.
