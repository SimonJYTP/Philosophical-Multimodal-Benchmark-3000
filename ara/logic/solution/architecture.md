# Architecture

The release pipeline selects traceable records from four upstream benchmarks, assigns content-aware splits, materializes source-mapped images, emits aligned complete/query/answer artifacts, and validates the resulting release independently.

Primary implementation: `scripts/build_dataset.py`; independent checks: `scripts/validate_release.py`; scoring: `scripts/evaluate.py`.
