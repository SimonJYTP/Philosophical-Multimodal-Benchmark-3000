from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from evaluate import choice, labels, rationale_score


ROOT = Path(__file__).resolve().parents[1]
HL_FAMILY = "scene_action_rationale"
VULCA_FAMILY = "philosophical_aesthetics_dimension_identification"
CHOICE_FAMILIES = {
    "visual_multiple_choice_qa",
    "moral_judge",
    "moral_classification",
    "moral_response",
}
MULTIMODAL_FAMILIES = [HL_FAMILY, *sorted(CHOICE_FAMILIES)]
ALL_FAMILIES = [*MULTIMODAL_FAMILIES, VULCA_FAMILY]
RANDOM_BASELINES = {
    "visual_multiple_choice_qa": 0.25,
    "moral_judge": 0.5,
    "moral_classification": 1 / 7,
    "moral_response": 0.5,
}
CSV_FIELDS = [
    "run_id",
    "provider",
    "model_id",
    "prompt_id",
    "condition",
    "language",
    "source",
    "family",
    "subgroup",
    "n_items",
    "metric",
    "estimate",
    "ci95_low",
    "ci95_high",
    "baseline",
    "delta_reference_run_id",
    "delta_estimate",
    "delta_ci95_low",
    "delta_ci95_high",
    "p_value",
    "p_adjusted",
    "correction_family",
    "notes",
]


def load_predictions(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        value = json.loads(text)
    else:
        value = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(value, list):
        raise ValueError("prediction file must be a JSON array or JSONL")
    return value


def parse_families(value: str) -> list[str]:
    if value == "multimodal":
        return MULTIMODAL_FAMILIES
    if value == "all":
        return ALL_FAMILIES
    output = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(output) - set(ALL_FAMILIES))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown task families: {unknown}")
    return output


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def quantile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def cluster_bootstrap(
    items: list[dict[str, Any]], metric: Callable[[list[dict[str, Any]]], float], samples: int, seed: int
) -> tuple[float, float]:
    if not items or samples < 1:
        return 0.0, 0.0
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[item["group_id"]].append(item)
    names = sorted(groups)
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        resampled = []
        for _ in names:
            resampled.extend(groups[rng.choice(names)])
        values.append(metric(resampled))
    return quantile(values, 0.025), quantile(values, 0.975)


def accuracy(items: list[dict[str, Any]]) -> float:
    return sum(item["prediction"] == item["gold"] for item in items) / len(items) if items else 0.0


def balanced_accuracy(items: list[dict[str, Any]], label_space: list[str]) -> float:
    recalls = []
    for label in label_space:
        positives = [item for item in items if item["gold"] == label]
        recalls.append(sum(item["prediction"] == label for item in positives) / len(positives) if positives else 0.0)
    return statistics.fmean(recalls) if recalls else 0.0


def multiclass_macro_f1(items: list[dict[str, Any]], label_space: list[str]) -> float:
    scores = []
    for label in label_space:
        tp = sum(item["prediction"] == label and item["gold"] == label for item in items)
        fp = sum(item["prediction"] == label and item["gold"] != label for item in items)
        fn = sum(item["prediction"] != label and item["gold"] == label for item in items)
        scores.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return statistics.fmean(scores) if scores else 0.0


def multilabel_scores(items: list[dict[str, Any]]) -> dict[str, float]:
    universe = sorted(set().union(*(item["prediction_labels"] | item["gold_labels"] for item in items))) if items else []
    tp = fp = fn = 0
    label_f1 = []
    for label in universe:
        label_tp = sum(label in item["prediction_labels"] and label in item["gold_labels"] for item in items)
        label_fp = sum(label in item["prediction_labels"] and label not in item["gold_labels"] for item in items)
        label_fn = sum(label not in item["prediction_labels"] and label in item["gold_labels"] for item in items)
        tp += label_tp
        fp += label_fp
        fn += label_fn
        label_f1.append(2 * label_tp / (2 * label_tp + label_fp + label_fn) if (2 * label_tp + label_fp + label_fn) else 0.0)
    return {
        "exact_match": sum(item["prediction_labels"] == item["gold_labels"] for item in items) / len(items) if items else 0.0,
        "micro_f1": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0,
        "macro_f1": statistics.fmean(label_f1) if label_f1 else 0.0,
    }


def make_row(meta: dict[str, str], source: str, family: str, n: int, metric: str, estimate: float,
             low: float | None, high: float | None, baseline: float | None = None, notes: str = "") -> dict[str, Any]:
    row = {field: "" for field in CSV_FIELDS}
    row.update(meta)
    row.update(
        {
            "source": source,
            "family": family,
            "subgroup": "all",
            "n_items": n,
            "metric": metric,
            "estimate": round(estimate, 6),
            "ci95_low": "" if low is None else round(low, 6),
            "ci95_high": "" if high is None else round(high, 6),
            "baseline": "" if baseline is None else round(baseline, 6),
            "notes": notes,
        }
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Publication-oriented PHILBENCH-3000 analysis.")
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--families", type=parse_families, default=MULTIMODAL_FAMILIES)
    parser.add_argument("--parsing", choices=("strict", "lenient"), default="strict")
    parser.add_argument("--allow-partial", action="store_true", help="Allow pilot files that do not cover the selected split")
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    benchmark = [json.loads(line) for line in (ROOT / "data" / "benchmark.jsonl").open(encoding="utf-8")]
    answers = {item["id"]: item["target"]["answer"] for item in json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))}
    expected = {
        item["id"]: item
        for item in benchmark
        if item["split"] == args.split and item["task"]["family"] in args.families
    }
    predictions = load_predictions(args.predictions)
    indexed = {item["id"]: item for item in predictions}
    if len(indexed) != len(predictions):
        raise SystemExit("duplicate prediction IDs")
    unknown = sorted(set(indexed) - set(expected))
    missing = sorted(set(expected) - set(indexed))
    if unknown:
        raise SystemExit(f"{len(unknown)} predictions are outside the selected split/families")
    if missing and not args.allow_partial:
        raise SystemExit(f"missing {len(missing)} predictions; use --allow-partial only for pilot analysis")

    manifest_path = args.predictions.parent / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    first = predictions[0] if predictions else {}
    meta = {
        "run_id": manifest.get("run_id") or first.get("run_id", "unknown"),
        "provider": manifest.get("provider", "unknown"),
        "model_id": manifest.get("model_id", "unknown"),
        "prompt_id": manifest.get("prompt_id", "unknown"),
        "condition": manifest.get("condition", "unknown"),
        "language": manifest.get("language", "unknown"),
    }

    prepared: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record_id, prediction_record in indexed.items():
        record = expected[record_id]
        family = record["task"]["family"]
        prediction = str(prediction_record.get("prediction", ""))
        if args.parsing == "strict" and prediction_record.get("parse_status", "strict_ok") != "strict_ok":
            prediction = ""
        item = {
            "id": record_id,
            "group_id": record["audit"]["group_id"],
            "source": record["source"]["benchmark"],
            "prediction": prediction,
            "gold": answers[record_id],
            "parse_failed": prediction_record.get("parse_status") == "failed",
            "refusal": bool(prediction_record.get("refusal", False)),
            "api_failure": bool(prediction_record.get("api_failure", False)),
        }
        if family in CHOICE_FAMILIES:
            item["prediction"] = choice(prediction)
            item["gold"] = choice(item["gold"])
        elif family == VULCA_FAMILY:
            item["prediction_labels"] = labels(prediction)
            item["gold_labels"] = labels(item["gold"])
        elif family == HL_FAMILY:
            item["score"] = rationale_score(prediction, item["gold"])
        prepared[family].append(item)

    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"metadata": meta, "split": args.split, "parsing": args.parsing, "families": {}}
    for family in args.families:
        items = prepared.get(family, [])
        if not items:
            continue
        source = items[0]["source"]
        family_summary: dict[str, Any] = {"source": source, "n_items": len(items)}
        if family in CHOICE_FAMILIES:
            correct = sum(item["prediction"] == item["gold"] for item in items)
            acc = correct / len(items)
            low, high = wilson(correct, len(items))
            label_space = sorted({item["gold"] for item in items})
            bacc = balanced_accuracy(items, label_space)
            macro = multiclass_macro_f1(items, label_space)
            b_low, b_high = cluster_bootstrap(items, lambda sample: balanced_accuracy(sample, label_space), args.bootstrap_samples, args.seed)
            f_low, f_high = cluster_bootstrap(items, lambda sample: multiclass_macro_f1(sample, label_space), args.bootstrap_samples, args.seed + 1)
            rows.append(make_row(meta, source, family, len(items), "accuracy", acc, low, high, RANDOM_BASELINES[family]))
            rows.append(make_row(meta, source, family, len(items), "balanced_accuracy", bacc, b_low, b_high))
            rows.append(make_row(meta, source, family, len(items), "macro_f1", macro, f_low, f_high))
            family_summary.update({"accuracy": acc, "accuracy_ci95": [low, high], "balanced_accuracy": bacc, "macro_f1": macro})
            family_summary["confusion"] = {
                gold: dict(Counter(item["prediction"] or "INVALID" for item in items if item["gold"] == gold))
                for gold in label_space
            }
        elif family == VULCA_FAMILY:
            scores = multilabel_scores(items)
            for index, (metric, estimate) in enumerate(scores.items()):
                low, high = cluster_bootstrap(items, lambda sample, name=metric: multilabel_scores(sample)[name], args.bootstrap_samples, args.seed + index)
                rows.append(make_row(meta, source, family, len(items), metric, estimate, low, high, notes="Text-only proxy; requires a published global L5 codebook"))
            family_summary.update(scores)
        else:
            estimate = statistics.fmean(item["score"] for item in items)
            low, high = cluster_bootstrap(items, lambda sample: statistics.fmean(item["score"] for item in sample), args.bootstrap_samples, args.seed)
            rows.append(make_row(meta, source, family, len(items), "mean_max_token_f1", estimate, low, high, notes="Lexical proxy; pair with blinded human ratings"))
            family_summary.update({"mean_max_token_f1": estimate, "ci95": [low, high]})

        for metric, key in (("parse_failure_rate", "parse_failed"), ("refusal_rate", "refusal"), ("api_failure_rate", "api_failure")):
            events = sum(item[key] for item in items)
            low, high = wilson(events, len(items))
            rate = events / len(items)
            rows.append(make_row(meta, source, family, len(items), metric, rate, low, high))
            family_summary[metric] = rate
        summary["families"][family] = family_summary

    output_dir = (args.output_dir or args.predictions.parent / "analysis").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "metrics_long.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        f"# PHILBENCH-3000 result: {meta['model_id']}",
        "",
        f"- Run: `{meta['run_id']}`",
        f"- Split: `{args.split}`",
        f"- Parsing: `{args.parsing}`",
        "",
        "| Family | n | Primary result | 95% CI |",
        "|---|---:|---:|---:|",
    ]
    for family, result in summary["families"].items():
        if "accuracy" in result:
            estimate, interval = result["accuracy"], result["accuracy_ci95"]
        elif "micro_f1" in result:
            estimate = result["micro_f1"]
            matching = next(row for row in rows if row["family"] == family and row["metric"] == "micro_f1")
            interval = [matching["ci95_low"], matching["ci95_high"]]
        else:
            estimate, interval = result["mean_max_token_f1"], result["ci95"]
        lines.append(f"| `{family}` | {result['n_items']} | {estimate:.4f} | [{float(interval[0]):.4f}, {float(interval[1]):.4f}] |")
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved analysis to {output_dir}")


if __name__ == "__main__":
    main()
