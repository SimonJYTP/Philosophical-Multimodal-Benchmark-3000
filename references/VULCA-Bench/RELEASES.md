# Release Reconciliation

## Canonical release candidate: v2.1

The current public release candidate is built from the controlled release source:

- source repository: `yha9806/vulca-emnlp2026`
- source ref: `paper/bench-emnlp2026-release`
- source commit used for export: `2e5ee33740fcf16f6000316c410287c03bbfb3af`
- source release manifest: `vulca_bench_release_v2_1_20260524`
- source manifest commit field: `427e8b63ae35428c206182108bf2cc7fdce9d233`
- canonical records: 7,236
- unique covered dimensions: 236

The source commit includes the provenance correction used to assemble this public candidate. No Git tag or hosted release is created by this reconciliation branch.

## Historical paper-era public snapshot

Public repository commit `cfb0a8cd68f7cd1007c469638e685d2a3c5aec1c` contains 7,410 JSONL records and 236 unique covered dimensions. Its README says 7,408 records. The arXiv v3 abstract reports 7,410 matched image-critique pairs and 225 fine-grained dimensions.

These differences are preserved as historical evidence. The v2.1 release does not claim that the earlier public snapshot, paper text, and current controlled release are identical.

## Hugging Face observation

The public Hugging Face dataset was observed at commit `27d68e76b61edc6ee4206e850f527cea7028964e` with 7,236 records and 236 unique dimensions. Its total count matches v2.1, but the observed culture counts differ by one classification:

| Culture | v2.1 source | Hugging Face observation |
| --- | ---: | ---: |
| Chinese | 1,994 | 1,995 |
| Western | 4,002 | 4,001 |

All other culture counts match. The Hugging Face surface also contains embedded image bytes, while the v2.1 rights manifest authorizes no image redistribution.

Status: **reconciliation required**. This branch records the divergence but does not mutate the Hugging Face dataset.

## Release rule

For v2.1 repository publication, `release/v2.1/manifest.json` and the files whose hashes it records are the canonical machine-readable boundary. Future hosted releases should be cut only after the validator passes and the separate Hugging Face rights decision is resolved.
