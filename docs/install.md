# Install

## From GitHub

```bash
pip install "media-cover-art @ git+https://github.com/schleising/media-cover-art.git@main"
```

Pin a tag once releases exist:

```bash
pip install "media-cover-art @ git+https://github.com/schleising/media-cover-art.git@v0.1.0"
```

## Editable local install

```bash
pip install -e /path/to/media-cover-art
pip install -e ".[dev,docs]"   # from the repo root
```

## Docker / requirements

```text
media-cover-art @ git+https://github.com/schleising/media-cover-art.git@main
```

Private-repo Docker builds need a deploy key or BuildKit secret (documented when publishing is configured).
