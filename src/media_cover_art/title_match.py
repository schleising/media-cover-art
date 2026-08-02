"""Ranked title matching for Arr / TMDB cover-art lookups.

Policy C (spinoff-safe):

1. Punctuation-folded exact match
2. Query tokens are a prefix / contained-as-words in the candidate (prefer longer)
3. Last resort: candidate is a prefix / contained in the query (parent franchise),
   still preferring the longest candidate
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .identity import normalize_title

_PUNCT_TO_SPACE = re.compile(r"[:\-'_.,/;\\|]+")
_NON_ALNUM_SPACE = re.compile(r"[^a-z0-9\s]+")
_MULTI_SPACE = re.compile(r"\s+")


def fold_title_for_match(value: str) -> str:
    """Normalize and fold punctuation so colons/dashes do not block equality.

    Args:
        value: Raw title from a path or provider.

    Returns:
        Folded lowercase title used by Policy C ranking.
    """
    cleaned = normalize_title(value)
    cleaned = _PUNCT_TO_SPACE.sub(" ", cleaned)
    cleaned = _NON_ALNUM_SPACE.sub(" ", cleaned)
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
    return cleaned


def titles_match_exact(left: str, right: str) -> bool:
    """Return True when two titles are equal after punctuation folding.

    Args:
        left: First title.
        right: Second title.

    Returns:
        Whether the folded forms are identical.
    """
    return fold_title_for_match(left) == fold_title_for_match(right)


def _word_boundary_contains(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    if haystack == needle:
        return True
    padded = f" {haystack} "
    return f" {needle} " in padded


def rank_title_match(query: str, candidate: str) -> tuple[int, int] | None:
    """Return a sortable score for candidate quality, or None if unrelated.

    Higher tuple is better: ``(tier, folded_length)``.

    - tier 3 = exact
    - tier 2 = query ⊆ candidate
    - tier 1 = candidate ⊆ query (parent franchise)

    Args:
        query: Title from the media path / identity.
        candidate: Title from Arr or TMDB.

    Returns:
        Sortable score tuple, or ``None`` when titles are unrelated.
    """
    needle = fold_title_for_match(query)
    normalized = fold_title_for_match(candidate)
    if not needle or not normalized:
        return None

    if needle == normalized:
        return (3, len(normalized))

    needle_tokens = needle.split()
    candidate_tokens = normalized.split()
    if not needle_tokens or not candidate_tokens:
        return None

    query_in_candidate = (
        len(needle_tokens) <= len(candidate_tokens)
        and candidate_tokens[: len(needle_tokens)] == needle_tokens
    ) or _word_boundary_contains(normalized, needle)

    candidate_in_query = (
        len(candidate_tokens) < len(needle_tokens)
        and needle_tokens[: len(candidate_tokens)] == candidate_tokens
    ) or (
        len(candidate_tokens) < len(needle_tokens)
        and _word_boundary_contains(needle, normalized)
    )

    if query_in_candidate:
        return (2, len(normalized))
    if candidate_in_query:
        return (1, len(normalized))
    return None


def pick_best_item_by_title(
    items: list[dict[str, Any]],
    title: str,
    year: int | None,
    *,
    candidate_titles: Callable[[dict[str, Any]], list[str]],
    item_year: Callable[[dict[str, Any]], int | None],
) -> dict[str, Any] | None:
    """Pick the best library/search item for title using Policy C ranking.

    Args:
        items: Provider result dicts (Arr library rows or TMDB search hits).
        title: Query title from media identity.
        year: Optional year filter; mismatched years are skipped when both set.
        candidate_titles: Extracts candidate title strings from an item.
        item_year: Extracts an optional year from an item.

    Returns:
        The best matching item, or ``None`` if nothing ranks.
    """
    best_item: dict[str, Any] | None = None
    best_score: tuple[int, int] | None = None

    for item in items:
        year_value = item_year(item)
        year_ok = year is None or year_value is None or int(year_value) == int(year)
        if not year_ok:
            continue

        item_best: tuple[int, int] | None = None
        for candidate in candidate_titles(item):
            if not candidate:
                continue
            score = rank_title_match(title, candidate)
            if score is None:
                continue
            if item_best is None or score > item_best:
                item_best = score

        if item_best is None:
            continue
        if best_score is None or item_best > best_score:
            best_score = item_best
            best_item = item

    return best_item
