from __future__ import annotations

import unittest

from media_cover_art import parse_media_identity


class MediaIdentityTests(unittest.TestCase):
    def test_film_from_folder_year(self) -> None:
        identity = parse_media_identity(
            "/Media/Films/1917 (2019)/1917 (2019) Bluray-1080p.mkv"
        )
        self.assertEqual(identity.kind, "film")
        self.assertEqual(identity.title, "1917")
        self.assertEqual(identity.year, 2019)
        self.assertEqual(identity.display_title, "1917 (2019)")
        self.assertEqual(identity.cache_key, "film:1917:2019")

    def test_film_from_basename_when_no_year_folder(self) -> None:
        identity = parse_media_identity(
            "/Media/Films/Some Movie/Some Movie 2018 WEBDL-1080p.mkv"
        )
        self.assertEqual(identity.kind, "film")
        self.assertEqual(identity.title, "Some Movie")
        self.assertIsNone(identity.year)
        self.assertEqual(identity.display_title, "Some Movie")

    def test_tv_series_poster_key_and_episode_display(self) -> None:
        identity = parse_media_identity(
            "/Media/TV/100 Foot Wave/Season 1/"
            "100 Foot Wave - S01E01 - Chapter I – Sea Monsters WEBDL-1080p.mkv"
        )
        self.assertEqual(identity.kind, "tv")
        self.assertEqual(identity.title, "100 Foot Wave")
        self.assertEqual(identity.season, 1)
        self.assertEqual(identity.episode, 1)
        self.assertEqual(identity.cache_key, "tvshow:100-foot-wave")
        self.assertIn("S01E01", identity.display_title)
        self.assertTrue(identity.display_title.startswith("100 Foot Wave"))
        self.assertEqual(
            identity.display_title,
            "100 Foot Wave · S01E01 · Chapter I – Sea Monsters",
        )

    def test_tv_strips_proper_and_repack_from_display(self) -> None:
        proper = parse_media_identity(
            "/Media/TV/Some Show/Season 2/"
            "Some Show - S02E04 - Cold Open PROPER WEBDL-1080p.mkv"
        )
        self.assertEqual(proper.display_title, "Some Show · S02E04 · Cold Open")
        self.assertEqual(proper.episode_title, "Cold Open")

        repack = parse_media_identity(
            "/Media/TV/Some Show/Season 2/"
            "Some Show - S02E05 - Finale REPACK BluRay-1080p.mkv"
        )
        self.assertEqual(repack.display_title, "Some Show · S02E05 · Finale")
        self.assertEqual(repack.episode_title, "Finale")

    def test_unknown_path(self) -> None:
        identity = parse_media_identity("/Media/Other/clip.mkv")
        self.assertEqual(identity.kind, "unknown")
        self.assertEqual(identity.display_title, "clip.mkv")
        self.assertTrue(identity.cache_key.startswith("unknown:"))


if __name__ == "__main__":
    unittest.main()
