from __future__ import annotations

import unittest
from typing import Any

from media_cover_art import (
    fold_title_for_match,
    pick_best_item_by_title,
    rank_title_match,
    titles_match_exact,
)


def find_item_by_title(
    items: list[dict[str, Any]],
    title: str,
    year: int | None = None,
) -> dict[str, Any] | None:
    """Mirror Arr candidate keys for unit tests."""

    def candidate_titles(item: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for key in ("title", "sortTitle", "cleanTitle"):
            value = item.get(key)
            if value:
                values.append(str(value))
        return values

    def item_year(item: dict[str, Any]) -> int | None:
        value = item.get("year")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return pick_best_item_by_title(
        items,
        title,
        year,
        candidate_titles=candidate_titles,
        item_year=item_year,
    )


class TitleMatchTests(unittest.TestCase):
    def test_fold_punctuation_equates_colon_variants(self) -> None:
        self.assertEqual(
            fold_title_for_match("Star Trek: Strange New Worlds"),
            fold_title_for_match("Star Trek Strange New Worlds"),
        )
        self.assertTrue(
            titles_match_exact(
                "The Walking Dead: Dead City",
                "The Walking Dead Dead City",
            )
        )

    def test_spinoff_beats_parent_star_trek(self) -> None:
        library = [
            {"title": "Star Trek", "year": 1966, "id": 1},
            {"title": "Star Trek: Strange New Worlds", "year": 2022, "id": 2},
            {"title": "Star Trek: Discovery", "year": 2017, "id": 3},
        ]
        match = find_item_by_title(library, "Star Trek Strange New Worlds")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match["id"], 2)
        self.assertEqual(match["title"], "Star Trek: Strange New Worlds")

    def test_spinoff_beats_parent_walking_dead(self) -> None:
        library = [
            {"title": "The Walking Dead", "year": 2010, "id": 10},
            {"title": "The Walking Dead: Dead City", "year": 2023, "id": 11},
            {"title": "Fear the Walking Dead", "year": 2015, "id": 12},
        ]
        match = find_item_by_title(library, "The Walking Dead Dead City")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match["id"], 11)

    def test_non_spinoff_control_exact(self) -> None:
        library = [
            {"title": "100 Foot Wave", "year": 2021, "id": 20},
            {"title": "Wave", "year": 2019, "id": 21},
        ]
        match = find_item_by_title(library, "100 Foot Wave")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match["id"], 20)

    def test_parent_query_still_matches_parent(self) -> None:
        library = [
            {"title": "Star Trek", "year": 1966, "id": 1},
            {"title": "Star Trek: Strange New Worlds", "year": 2022, "id": 2},
        ]
        match = find_item_by_title(library, "Star Trek")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match["id"], 1)

    def test_rank_tiers(self) -> None:
        exact = rank_title_match(
            "Star Trek Strange New Worlds",
            "Star Trek: Strange New Worlds",
        )
        parent = rank_title_match("Star Trek Strange New Worlds", "Star Trek")
        self.assertIsNotNone(exact)
        self.assertIsNotNone(parent)
        assert exact is not None and parent is not None
        self.assertEqual(exact[0], 3)
        self.assertEqual(parent[0], 1)
        self.assertIsNone(rank_title_match("100 Foot Wave", "Star Trek"))

    def test_pick_best_uses_custom_title_keys(self) -> None:
        results = [
            {"name": "The Walking Dead", "id": 1},
            {
                "name": "The Walking Dead: Dead City",
                "original_name": "Dead City",
                "id": 2,
            },
        ]
        match = pick_best_item_by_title(
            results,
            "The Walking Dead Dead City",
            None,
            candidate_titles=lambda item: [
                str(item[key])
                for key in ("name", "original_name")
                if item.get(key)
            ],
            item_year=lambda _item: None,
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match["id"], 2)


if __name__ == "__main__":
    unittest.main()
