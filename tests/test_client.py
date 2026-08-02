from __future__ import annotations

from pathlib import Path

import mongomock
import pytest
import respx
from httpx import Response

from media_cover_art import CoverArtClient, CoverArtSettings


@pytest.fixture
def mongo_collection():
    client = mongomock.MongoClient()
    return client["media"]["cover_art_cache"]


@pytest.fixture
def settings(tmp_path: Path) -> CoverArtSettings:
    return CoverArtSettings(
        sonarr_url="http://sonarr.test",
        radarr_url="http://radarr.test",
        sonarr_api_key="sonarr-key",
        radarr_api_key="radarr-key",
        tmdb_api_key="tmdb-key",
        mongo_uri="mongodb://localhost:27017/",
        cache_dir=None,
    )


@pytest.fixture
def settings_with_cache(tmp_path: Path, settings: CoverArtSettings) -> CoverArtSettings:
    return CoverArtSettings(
        **{
            **settings.__dict__,
            "cache_dir": tmp_path / "art",
        }
    )


@respx.mock
def test_ensure_posters_film_radarr_metadata_only(
    settings: CoverArtSettings, mongo_collection
) -> None:
    respx.get("http://radarr.test/api/v3/movie").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "tmdbId": 581734,
                    "title": "1917",
                    "year": 2019,
                    "images": [
                        {
                            "coverType": "poster",
                            "remoteUrl": "https://cdn.example/1917.jpg",
                        }
                    ],
                }
            ],
        )
    )
    client = CoverArtClient(settings, collection=mongo_collection)
    records = client.ensure_posters(
        ["/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"]
    )
    assert len(records) == 1
    assert records[0].status == "ready"
    assert records[0].provider == "radarr"
    assert records[0].remote_url == "https://cdn.example/1917.jpg"
    assert records[0].local_path is None
    assert records[0].cache_key == "film:1917:2019"
    client.close()


@respx.mock
def test_ensure_posters_writes_local_when_cache_dir_set(
    settings_with_cache: CoverArtSettings, mongo_collection
) -> None:
    respx.get("http://radarr.test/api/v3/movie").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "tmdbId": 581734,
                    "title": "1917",
                    "year": 2019,
                    "images": [
                        {
                            "coverType": "poster",
                            "remoteUrl": "https://cdn.example/1917.jpg",
                        }
                    ],
                }
            ],
        )
    )
    respx.get("https://cdn.example/1917.jpg").mock(
        return_value=Response(
            200, content=b"jpeg-bytes", headers={"Content-Type": "image/jpeg"}
        )
    )
    client = CoverArtClient(settings_with_cache, collection=mongo_collection)
    records = client.ensure_posters(
        ["/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"]
    )
    assert records[0].status == "ready"
    assert records[0].local_path is not None
    assert Path(records[0].local_path).is_file()
    client.close()


@respx.mock
def test_tmdb_fallback_when_arr_empty(
    settings: CoverArtSettings, mongo_collection
) -> None:
    respx.get("http://radarr.test/api/v3/movie").mock(return_value=Response(200, json=[]))
    respx.get("http://radarr.test/api/v3/movie/lookup").mock(
        return_value=Response(200, json=[])
    )
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "id": 581734,
                        "title": "1917",
                        "release_date": "2019-12-25",
                        "poster_path": "/poster.jpg",
                    }
                ]
            },
        )
    )
    client = CoverArtClient(settings, collection=mongo_collection)
    records = client.ensure_posters(
        ["/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"]
    )
    assert records[0].status == "ready"
    assert records[0].provider == "tmdb"
    assert records[0].remote_url is not None
    assert records[0].remote_url.endswith("/poster.jpg")
    client.close()


@respx.mock
def test_hydrate_on_resolve_for_display(
    settings_with_cache: CoverArtSettings, mongo_collection
) -> None:
    # Seed metadata-only ready row (as Walker would write)
    client = CoverArtClient(settings_with_cache, collection=mongo_collection)
    path = "/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"
    respx.get("http://radarr.test/api/v3/movie").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "tmdbId": 581734,
                    "title": "1917",
                    "year": 2019,
                    "images": [
                        {
                            "coverType": "poster",
                            "remoteUrl": "https://cdn.example/1917.jpg",
                        }
                    ],
                }
            ],
        )
    )
    # First ensure without downloading by using metadata-only settings briefly
    meta_settings = CoverArtSettings(**{**settings_with_cache.__dict__, "cache_dir": None})
    meta_client = CoverArtClient(meta_settings, collection=mongo_collection)
    meta_client.ensure_posters([path])
    meta_client.close()

    respx.get("https://cdn.example/1917.jpg").mock(
        return_value=Response(
            200, content=b"jpeg-bytes", headers={"Content-Type": "image/jpeg"}
        )
    )
    fields = client.resolve_for_display(path)
    assert fields.cover_art_status == "ready"
    assert fields.cover_art_url.startswith("art/")
    record = client.get_ready_record(path)
    assert record is not None
    assert record.local_path is not None
    assert Path(record.local_path).is_file()
    client.close()


def test_unknown_path_skipped(settings: CoverArtSettings, mongo_collection) -> None:
    client = CoverArtClient(settings, collection=mongo_collection)
    assert client.ensure_posters(["/Media/Other/clip.mkv"]) == []
    client.close()
