# Concepts

- **Local-image coverage**: records with a non-null repository-relative image path whose file exists and has a recognized image signature.
- **Duplicate visual content**: image files sharing the same SHA-256 digest, independent of filename or task.
- **Blind query**: the inference artifact containing only `id`, `split`, `task`, and `input`, with targets and answer-correlated metadata removed.
- **HL enrichment tier**: HL records with one direct action/rationale theme match and official confidence at least 4.5; scene-only matches are excluded.
