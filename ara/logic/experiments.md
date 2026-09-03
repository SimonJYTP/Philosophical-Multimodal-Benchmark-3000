# Experiments

## E01: v5 release validation

Rebuild the full release twice, compare deterministic metadata hashes, validate all 3,000 records against the JSON Schema, verify every local image path/signature/SHA-256, audit split isolation, and replay the test answer key through the evaluator.

Result: passed. See `../evidence/tables/2026-09-03_release_validation.md`.
