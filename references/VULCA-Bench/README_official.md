# VULCA Cultural Visual Benchmark

VULCA-Bench is a metadata-first benchmark for evaluating culturally grounded visual critique across eight art traditions.

The current canonical public release candidate is **v2.1**:

- 7,236 critique records
- 8 cultural traditions
- 236 unique covered dimensions
- 7,236 unique `pair_id` values and 7,236 unique `ulid` values
- 0 artwork image files redistributed in this repository

The benchmark paper is available on [arXiv](https://arxiv.org/abs/2601.07986). The Hugging Face dataset is a separate distribution surface and is being reconciled against this release; see [RELEASES.md](RELEASES.md).

## Release contents

| Path | Purpose |
| --- | --- |
| `data/vulca_bench.jsonl` | Canonical v2.1 metadata and critique records |
| `data/culture_subsets/*.jsonl` | Exact per-culture partitions of the canonical file |
| `data/license_rights_manifest_v2_1.csv` | Row-level image-rights and annotation-license boundary |
| `release/v2.1/manifest.json` | Machine-readable counts, provenance, and artifact hashes |
| `scripts/validate_release.py` | Reproducible release-integrity checks |
| `evaluation/` | DCR and layer-scoring utilities |

## Culture counts

| Culture | Records |
| --- | ---: |
| Western | 4,002 |
| Chinese | 1,994 |
| Japanese | 383 |
| Hermitage | 196 |
| Mural | 190 |
| Islamic | 165 |
| Indian | 155 |
| Korean | 151 |
| **Total** | **7,236** |

## Validate the release

No third-party package is required for the release validator or its tests.

```bash
python3 scripts/validate_release.py
python3 -m unittest discover -s tests -v
```

The validator checks artifact hashes, row counts, schema invariants, identifier uniqueness, culture subsets, the rights manifest, relative image references, and the absence of redistributed image files.

## Data shape

Each JSONL record contains identifiers, cultural grouping, descriptive metadata, bilingual critiques, and a native JSON array of covered dimensions. Some descriptive fields such as `medium`, `art_style`, and `art_genre` are optional in the controlled source. `image_path` is a relative source-side reference; it is not proof of ownership, a retrieval URL, or permission to redistribute an image.

```json
{
  "pair_id": "…",
  "ulid": "…",
  "culture": "chinese",
  "image_path": "…",
  "artist": "…",
  "title": "…",
  "critique_zh": "…",
  "critique_en": "…",
  "covered_dimensions": ["…"]
}
```

See [IMAGE_RIGHTS.md](IMAGE_RIGHTS.md) before retrieving or using any artwork image.

## Evaluation

```bash
python evaluation/run_vlm.py --model gpt-4o --input data/vulca_bench.jsonl --output results/
python evaluation/calculate_dcr.py --input results/gpt-4o_results.jsonl --output dcr_scores.json
python evaluation/layer_scorer.py --input results/gpt-4o_results.jsonl --output layer_scores.json
```

Provider-specific dependencies and credentials are required only for model inference. Do not commit API keys or generated results containing restricted source material.

## Version boundary

The earlier public repository state contained 7,410 records and is retained in Git history as a paper-era snapshot. It is not silently rewritten into v2.1. Counts in the paper, historical repository, current release source, and Hugging Face surface are documented separately in [RELEASES.md](RELEASES.md).

## Citation

```bibtex
@article{yu2026vulcabench,
  title={VULCA-Bench: A Multi-Cultural Art Critique Benchmark for Vision-Language Models},
  author={Yu, Haorui and Yang, Diji and He, Hang and Zhang, Fengrui and Yi, Qiufeng},
  journal={arXiv preprint arXiv:2601.07986},
  year={2026}
}
```

## License

Benchmark metadata, critiques, codebooks, validation logs, split definitions, and scripts are released under [CC BY 4.0](LICENSE). Artwork images are not relicensed by VULCA and are not redistributed in this repository. Their rights remain source-specific; see [IMAGE_RIGHTS.md](IMAGE_RIGHTS.md).
