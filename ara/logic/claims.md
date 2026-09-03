# Claims

## C01: v5 exceeds the requested multimodal coverage threshold
- **Statement**: Release `3000-image-rich-v5` contains exactly 3,000 records and 2,591 locally readable source-mapped images, for 86.3667% coverage.
- **Status**: supported
- **Provenance**: ai-suggested
- **Falsification criteria**: Any aligned release file has a row count other than 3,000, fewer than 2,591 valid local image paths exist, or computed coverage is not greater than 80%.
- **Proof**: [`../evidence/tables/2026-09-03_release_validation.md`, `../../dataset_card.json`]
- **Dependencies**: []
- **Tags**: dataset-scale, multimodal-coverage, release-v5

## C02: duplicate visual content is isolated across splits
- **Statement**: The 2,591 local image records resolve to 2,440 unique SHA-256 contents; all 151 duplicate-content groups are confined to one train/dev/test split.
- **Status**: supported
- **Provenance**: ai-suggested
- **Falsification criteria**: A single image SHA-256 appears in more than one release split.
- **Proof**: [`../evidence/tables/2026-09-03_release_validation.md`, `../../dataset_card.json`]
- **Dependencies**: [C01]
- **Tags**: leakage-control, image-hash, split-integrity

## C03: MM-MoralBench sampling is foundation-task balanced
- **Statement**: The 1,680 selected MM-MoralBench records contain 280 records for each of six moral foundations, with 140 judge, 70 classification, and 70 response records per foundation.
- **Status**: supported
- **Provenance**: ai-suggested
- **Falsification criteria**: Any foundation-task stratum differs from its declared quota.
- **Proof**: [`../evidence/tables/2026-09-03_release_validation.md`, `../../dataset_card.json`]
- **Dependencies**: [C01]
- **Tags**: stratification, moral-foundations, task-balance
