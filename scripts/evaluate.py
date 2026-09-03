from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO_FAMILIES = {
    "visual_multiple_choice_qa",
    "moral_judge",
    "moral_classification",
    "moral_response",
    "philosophical_aesthetics_dimension_identification",
}


def load_predictions(path: str) -> list[dict]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def choice(value: object) -> str:
    match = re.fullmatch(r"\s*\(?([A-Ga-g])\)?\s*", str(value))
    return match.group(1).upper() if match else ""


def labels(value: object) -> set[str]:
    return set(re.findall(r"[A-Z]+_L5_D\d+", str(value).upper()))


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Score blind predictions for PHILBENCH-3000.")
    parser.add_argument("predictions", help="JSON/JSONL file, or '-' for stdin; rows need id and prediction")
    parser.add_argument("--split", choices=("train", "dev", "test", "all"), default="test")
    args = parser.parse_args()

    answers = json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))
    records = {
        record["id"]: record
        for line in (ROOT / "data" / "benchmark.jsonl").open(encoding="utf-8")
        if (record := json.loads(line)) and (args.split == "all" or record["split"] == args.split)
    }
    predictions = load_predictions(args.predictions)
    predicted = {item["id"]: item["prediction"] for item in predictions}
    if len(predicted) != len(predictions):
        raise SystemExit("duplicate prediction IDs")
    unknown = sorted(set(predicted) - set(records))
    missing = sorted(set(records) - set(predicted))
    if unknown or missing:
        raise SystemExit(f"prediction IDs do not match {args.split} split: unknown={len(unknown)}, missing={len(missing)}")

    gold = {item["id"]: item["target"]["answer"] for item in answers if item["id"] in records}
    choice_scores: dict[str, list[bool]] = defaultdict(list)
    vulca_pairs: list[tuple[set[str], set[str]]] = []
    manual = 0
    for record_id, record in records.items():
        family = record["task"]["family"]
        if family not in AUTO_FAMILIES:
            manual += 1
        elif record["task"]["output_type"] == "choice":
            choice_scores[family].append(choice(predicted[record_id]) == choice(gold[record_id]))
        else:
            vulca_pairs.append((labels(predicted[record_id]), labels(gold[record_id])))

    label_names = sorted(set().union(*(prediction | expected for prediction, expected in vulca_pairs))) if vulca_pairs else []
    label_f1 = []
    true_positive = false_positive = false_negative = 0
    for name in label_names:
        tp = sum(name in prediction and name in expected for prediction, expected in vulca_pairs)
        fp = sum(name in prediction and name not in expected for prediction, expected in vulca_pairs)
        fn = sum(name not in prediction and name in expected for prediction, expected in vulca_pairs)
        true_positive += tp
        false_positive += fp
        false_negative += fn
        label_f1.append(ratio(2 * tp, 2 * tp + fp + fn))

    result = {
        "split": args.split,
        "prediction_count": len(predicted),
        "choice_accuracy": {
            family: {"count": len(values), "accuracy": ratio(sum(values), len(values))}
            for family, values in sorted(choice_scores.items())
        },
        "vulca_l5": {
            "count": len(vulca_pairs),
            "exact_match": ratio(sum(prediction == expected for prediction, expected in vulca_pairs), len(vulca_pairs)),
            "micro_f1": ratio(2 * true_positive, 2 * true_positive + false_positive + false_negative),
            "macro_f1": round(sum(label_f1) / len(label_f1), 6) if label_f1 else 0.0,
        },
        "manual_or_semantic_scoring_required": {
            "family": "scene_action_rationale",
            "count": manual,
            "reason": "Free-text rationales require a declared semantic metric and/or human rubric.",
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
