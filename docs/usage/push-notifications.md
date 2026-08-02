# Push notifications

Conversion-complete web push should use the public HTTPS `remote_url` from a ready cache row (not the auth-gated Converter art endpoint).

```python
from media_cover_art import CoverArtClient, CoverArtSettings

with CoverArtClient(CoverArtSettings.from_env(), collection=coll) as client:
    record = client.get_ready_record(source_path)
    if record and record.remote_url and record.remote_url.startswith("https://"):
        icon = image = record.remote_url
```

Walker prefetch warms these rows before conversion finishes, so notifications can show posters even if the Converter UI was never opened.
