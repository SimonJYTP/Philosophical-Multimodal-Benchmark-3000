# Heuristics

## H01: Raise image coverage through eligible visual sources
- **Rationale**: Use every HL record that already satisfies declared evidence rules and expand MM from its complete official image-mapped query set, while reducing the text-only VULCA proxy share. This raises genuine multimodal coverage without weakening selection rules or fabricating images.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`scripts/build_dataset.py`]

## H02: Split on content hashes, not filenames
- **Rationale**: Different records and filenames can reuse identical image bytes; SHA-256 grouping prevents this latent visual leakage across evaluation splits.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`scripts/build_dataset.py`, `scripts/validate_release.py`]
