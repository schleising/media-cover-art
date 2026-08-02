# Walker usage

!!! note "Phase 2"
    Walker integration (`ensure_posters` after new-file discovery) lands after the sync client.

Intended call site: convert-to-h265 `CodecDetector` after a successful bulk upsert of new paths.
