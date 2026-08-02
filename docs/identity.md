# Identity & matching

## Path → identity

`parse_media_identity` derives `kind`, `title`, `year` / season / episode, `display_title`, and `cache_key` from full media paths.

| Path signal | Result |
| ----------- | ------ |
| Contains `Films` | `kind=film`, key `film:{slug}` or `film:{slug}:{year}` |
| Contains `TV` | `kind=tv`, key `tvshow:{slug}` (series poster) |
| Else | `kind=unknown` (no remote lookup) |

## Policy C title matching

Spinoff-safe ranking used by Arr/TMDB pickers:

1. Punctuation-folded exact match
2. Query ⊆ candidate (prefer longer)
3. Candidate ⊆ query (parent franchise), still longest

See `fold_title_for_match`, `rank_title_match`, and `pick_best_item_by_title` in the [API reference](api.md).
