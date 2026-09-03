from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from analyze_results import MULTIMODAL_FAMILIES, cluster_bootstrap, load_predictions, parse_families
from evaluate import choice, labels, rationale_score


ROOT = Path(__file__).resolve().parents[1]
HL_FAMILY = "scene_action_rationale"
VULCA_FAMILY = "philosophical_aesthetics_dimension_identification"
CHOICE_FAMILIES = set(MULTIMODAL_FAMILIES) - {HL_FAMILY}


def manifest_for(path: Path) -> dict[str, Any]:
    candidate = path.parent / "run_manifest.json"
    return json.loads(candidate.read_text(encoding="utf-8")) if candidate.is_file() else {}


def normalized_prediction(row: dict[str, Any], family: str, parsing: str) -> str:
    if parsing == "strict" and row.get("parse_status", "strict_ok") != "strict_ok":
        return ""
    value = str(row.get("prediction", ""))
    return choice(value) if family in CHOICE_FAMILIES else value


def sample_score(family: str, prediction: str, gold: str) -> float:
    if family in CHOICE_FAMILIES:
        return float(prediction == choice(gold))
    if family == HL_FAMILY:
        return rationale_score(prediction, gold)
    predicted_labels = labels(prediction)
    gold_labels = labels(gold)
    denominator = len(predicted_labels) + len(gold_labels)
    return 2 * len(predicted_labels & gold_labels) / denominator if denominator else 0.0


def exact_mcnemar(discordant_baseline: int, discordant_treatment: int) -> float:
    total = discordant_baseline + discordant_treatment
    if total == 0:
        return 1.0
    tail = min(discordant_baseline, discordant_treatment)
    probability = sum(math.comb(total, k) for k in range(tail + 1)) / (2**total)
    return min(1.0, 2 * probability)


def holm(pairs: list[tuple[str, float]]) -> dict[str, float]:
    ordered = sorted(pairs, key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * value))
        adjusted[name] = running
    return adjusted


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired comparison of two PHILBENCH-3000 runs.")
    parser.add_argument("baseline", type=Path, help="Baseline predictions.jsonl")
    parser.add_argument("treatment", type=Path, help="Treatment predictions.jsonl; delta is treatment minus baseline")
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--families", type=parse_families, default=MULTIMODAL_FAMILIES)
    parser.add_argument("--parsing", choices=("strict", "lenient"), default="strict")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    baseline_list = load_predictions(args.baseline)
    treatment_list = load_predictions(args.treatment)
    baseline_rows = {row["id"]: row for row in baseline_list}
    treatment_rows = {row["id"]: row for row in treatment_list}
    if len(baseline_rows) != len(baseline_list) or len(treatment_rows) != len(treatment_list):
        raise SystemExit("duplicate prediction IDs")

    benchmark = {
        row["id"]: row
        for line in (ROOT / "data" / "benchmark.jsonl").open(encoding="utf-8")
        if (row := json.loads(line)) and row["split"] == args.split and row["task"]["family"] in args.families
    }
    answers = {item["id"]: item["target"]["answer"] for item in json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))}
    expected_ids = set(benchmark)
    common = set(baseline_rows) & set(treatment_rows) & expected_ids
    outside = (set(baseline_rows) | set(treatment_rows)) - expected_ids
    if outside:
        raise SystemExit(f"{len(outside)} predictions are outside the selected split/families")
    if not args.allow_partial and (set(baseline_rows) != expected_ids or set(treatment_rows) != expected_ids):
        raise SystemExit("both runs must completely cover the selected split/families")
    if not common:
        raise SystemExit("the two runs have no comparable predictions")

    baseline_manifest = manifest_for(args.baseline)
    treatment_manifest = manifest_for(args.treatment)
    items_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record_id in sorted(common):
        record = benchmark[record_id]
        family = record["task"]["family"]
        baseline_prediction = normalized_prediction(baseline_rows[record_id], family, args.parsing)
        treatment_prediction = normalized_prediction(treatment_rows[record_id], family, args.parsing)
        baseline_score = sample_score(family, baseline_prediction, answers[record_id])
        treatment_score = sample_score(family, treatment_prediction, answers[record_id])
        items_by_family[family].append(
            {
                "id": record_id,
                "group_id": record["audit"]["group_id"],
                "baseline_score": baseline_score,
                "treatment_score": treatment_score,
                "delta": treatment_score - baseline_score,
            }
        )

    results = []
    p_values = []
    for family in args.families:
        items = items_by_family.get(family, [])
        if not items:
            continue
        baseline_estimate = statistics.fmean(item["baseline_score"] for item in items)
        treatment_estimate = statistics.fmean(item["treatment_score"] for item in items)
        delta = treatment_estimate - baseline_estimate
        low, high = cluster_bootstrap(
            items,
            lambda sample: statistics.fmean(item["delta"] for item in sample),
            args.bootstrap_samples,
            args.seed,
        )
        metric = "accuracy" if family in CHOICE_FAMILIES else ("mean_max_token_f1" if family == HL_FAMILY else "mean_sample_f1")
        p_value = None
        if family in CHOICE_FAMILIES:
            baseline_only = sum(item["baseline_score"] == 1 and item["treatment_score"] == 0 for item in items)
            treatment_only = sum(item["baseline_score"] == 0 and item["treatment_score"] == 1 for item in items)
            p_value = exact_mcnemar(baseline_only, treatment_only)
            p_values.append((family, p_value))
        results.append(
            {
                "family": family,
                "n_items": len(items),
                "metric": metric,
                "baseline_estimate": baseline_estimate,
                "treatment_estimate": treatment_estimate,
                "delta": delta,
                "delta_ci95": [low, high],
                "mcnemar_exact_p": p_value,
                "holm_adjusted_p": None,
            }
        )

    adjusted = holm(p_values)
    for result in results:
        if result["family"] in adjusted:
            result["holm_adjusted_p"] = adjusted[result["family"]]

    output = {
        "split": args.split,
        "parsing": args.parsing,
        "baseline_run_id": baseline_manifest.get("run_id", "unknown"),
        "treatment_run_id": treatment_manifest.get("run_id", "unknown"),
        "results": results,
        "notes": [
            "Confidence intervals use paired group_id cluster bootstrap.",
            "McNemar p values are reported only for choice tasks and Holm-adjusted across those task families.",
            "VULCA comparison uses mean per-item label F1, not corpus micro-F1.",
        ],
    }
    output_dir = (args.output_dir or args.treatment.parent / "comparison_to_baseline").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "metrics_delta.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["baseline_run_id", "treatment_run_id", "family", "n_items", "metric", "baseline_estimate", "treatment_estimate", "delta", "delta_ci95_low", "delta_ci95_high", "mcnemar_exact_p", "holm_adjusted_p"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "baseline_run_id": output["baseline_run_id"],
                    "treatment_run_id": output["treatment_run_id"],
                    **{key: value for key, value in result.items() if key != "delta_ci95"},
                    "delta_ci95_low": result["delta_ci95"][0],
                    "delta_ci95_high": result["delta_ci95"][1],
                }
            )
    lines = [
        "# PHILBENCH-3000 paired run comparison",
        "",
        f"- Baseline: `{output['baseline_run_id']}`",
        f"- Treatment: `{output['treatment_run_id']}`",
        "",
        "| Family | n | Baseline | Treatment | Delta | 95% CI | Holm p |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        low, high = result["delta_ci95"]
        adjusted_p = "—" if result["holm_adjusted_p"] is None else f"{result['holm_adjusted_p']:.4g}"
        lines.append(
            f"| `{result['family']}` | {result['n_items']} | {result['baseline_estimate']:.4f} | "
            f"{result['treatment_estimate']:.4f} | {result['delta']:+.4f} | [{low:+.4f}, {high:+.4f}] | {adjusted_p} |"
        )
    (output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Saved comparison to {output_dir}")


if __name__ == "__main__":
    main()
