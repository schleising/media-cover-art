#!/usr/bin/env python3
"""CLI helper: ensure posters for one or more media paths.

Requires network access to Arr/TMDB and Mongo as configured by env.
"""

from __future__ import annotations

import argparse
import json
import sys

from media_cover_art import CoverArtClient, CoverArtSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Full media paths")
    parser.add_argument(
        "--keys-file",
        help="Optional arr-keys.txt path (sonarr_key=… / radarr_key=… / tmdb_key=…)",
    )
    args = parser.parse_args(argv)

    settings = CoverArtSettings.from_env(keys_file=args.keys_file)
    with CoverArtClient(settings) as client:
        records = client.ensure_posters(args.paths)
    for record in records:
        print(
            json.dumps(
                {
                    "cache_key": record.cache_key,
                    "status": record.status,
                    "provider": record.provider,
                    "remote_url": record.remote_url,
                    "local_path": record.local_path,
                    "matched_title": record.matched_title,
                    "error_detail": record.error_detail,
                },
                indent=2,
            )
        )
    return 0 if records else 1


if __name__ == "__main__":
    sys.exit(main())
