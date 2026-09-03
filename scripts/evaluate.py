from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RATIONALE_FAMILY = "scene_action_rationale"

# 预先声明的 HL 自由文本评分指标（v5.1）
# ----------------------------------------
# metric: max-reference token F1（词汇级，确定性，纯标准库实现）
#   1. 参考答案按 "；" 拆分为多条人工 rationale；
#   2. 预测与每条参考分别计算 token 级 F1（英文按空白/分词字符切分，中文按字符
#      bigram 切分），取最大值作为该样本得分；
#   3. 数据集得分为全部样本均值。
# 该指标是预先注册的词汇级代理指标，用于跨模型横向比较与回归监控；
# 它不能替代人工量表或语义相似度评估，论文报告时应同时给出人工/语义评分。
def _tokens(text: str) -> list[str]:
    """英文/数字按词切分，连续中文按字符 bigram 切分（单字则保留单字）。"""
    tokens: list[str] = []
    for run in re.findall(r"[a-z0-9]+|[一-鿿]+", str(text).lower()):
        if re.fullmatch(r"[一-鿿]+", run):
            if len(run) == 1:
                tokens.append(run)
            else:
                tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
        else:
            tokens.append(run)
    return tokens


def token_f1(prediction: object, reference: object) -> float:
    pred_tokens = _tokens(str(prediction))
    ref_tokens = _tokens(str(reference))
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = defaultdict(int)
    for token in pred_tokens:
        common[token] += 1
    overlap = 0
    for token in ref_tokens:
        if common[token] > 0:
            common[token] -= 1
            overlap += 1
    if not overlap:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def rationale_score(prediction: object, gold: object) -> float:
    references = [ref.strip() for ref in str(gold).split("；") if ref.strip()]
    if not references:
        return 0.0
    return max(token_f1(prediction, ref) for ref in references)


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
    rationale_scores: list[float] = []
    for record_id, record in records.items():
        family = record["task"]["family"]
        if family == RATIONALE_FAMILY:
            rationale_scores.append(rationale_score(predicted[record_id], gold[record_id]))
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
        "hl_rationale": {
            "count": len(rationale_scores),
            "metric": "max-reference token F1 (pre-declared lexical proxy)",
            "mean_max_token_f1": round(sum(rationale_scores) / len(rationale_scores), 6) if rationale_scores else 0.0,
            "note": "Lexical proxy for cross-model comparison only; pair with a human rubric or declared semantic metric for publication-grade claims.",
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
