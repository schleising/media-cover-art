from __future__ import annotations

import logging

from media_cover_art import CoverArtSettings


def test_from_env_reports_env_key_sources(
    monkeypatch, caplog, tmp_path
) -> None:
    monkeypatch.setenv("SONARR_API_KEY", "sonarr-secret")
    monkeypatch.setenv("RADARR_API_KEY", "radarr-secret")
    monkeypatch.delenv("TMDB_API_KEY", raising=False)

    with caplog.at_level(logging.INFO, logger="media_cover_art.config"):
        settings = CoverArtSettings.from_env()
        settings.log_key_status()

    assert settings.sonarr_api_key_source == "environment SONARR_API_KEY"
    assert settings.radarr_api_key_source == "environment RADARR_API_KEY"
    assert settings.tmdb_api_key is None
    assert "Sonarr API key found (environment SONARR_API_KEY)" in caplog.text
    assert "Radarr API key found (environment RADARR_API_KEY)" in caplog.text
    assert "TMDB API key not found" in caplog.text


def test_from_env_reports_keys_file_sources(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.delenv("SONARR_API_KEY", raising=False)
    monkeypatch.delenv("RADARR_API_KEY", raising=False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    keys_file = tmp_path / "arr-keys.txt"
    keys_file.write_text(
        "sonarr_key=from-file-sonarr\nradarr_key=from-file-radarr\ntmdb_key=from-file-tmdb\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO, logger="media_cover_art.config"):
        settings = CoverArtSettings.from_env(keys_file=keys_file)
        settings.log_key_status()

    assert settings.keys_file_path == str(keys_file)
    assert "Arr keys file found:" in caplog.text
    assert "Sonarr API key found" in caplog.text
    assert "Radarr API key found" in caplog.text
    assert "TMDB API key found" in caplog.text
