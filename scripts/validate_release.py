from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2800-image-rich-v4"
EXPECTED_SOURCES = {
    "HL Dataset": 650,
    "HSSBench": 182,
    "MM-MoralBench": 1080,
    "VULCA-Bench": 888,
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def release_query(record: dict) -> dict:
    image = dict(record["input"]["image"])
    if image.get("path"):
        image.pop("original_reference", None)
    return {
        "id": record["id"],
        "split": record["split"],
        "task": record["task"],
        "input": {**record["input"], "image": image},
    }


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def valid_image_signature(path: Path) -> bool:
    header = path.read_bytes()[:12]
    return (
        header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"GIF8")
        or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
    )


def main() -> None:
    records = read_jsonl(ROOT / "data" / "benchmark.jsonl")
    queries = json.loads((ROOT / "data" / "query.json").read_text(encoding="utf-8"))
    answers = json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))
    card = json.loads((ROOT / "dataset_card.json").read_text(encoding="utf-8"))
    json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))

    ids = [record["id"] for record in records]
    check(len(records) == len(queries) == len(answers) == 2800, "release files must contain 2,800 aligned rows")
    check(len(ids) == len(set(ids)), "record IDs must be unique")
    check(Counter(record["source"]["benchmark"] for record in records) == Counter(EXPECTED_SOURCES), "source quotas changed")
    check(queries == [release_query(record) for record in records], "query.json is stale or leaks hidden metadata")
    check(
        answers == [{"id": record["id"], "split": record["split"], "target": record["target"]} for record in records],
        "answer_key.json is not exactly aligned with benchmark.jsonl",
    )

    split_rows = {name: read_jsonl(ROOT / "splits" / f"{name}.jsonl") for name in ("train", "dev", "test")}
    for name, rows in split_rows.items():
        check(rows == [record for record in records if record["split"] == name], f"{name}.jsonl is stale")

    group_splits: dict[str, set[str]] = defaultdict(set)
    image_hash_splits: dict[str, set[str]] = defaultdict(set)
    local_image_count = 0
    for record in records:
        check(record["audit"]["selection_version"] == VERSION, f"stale version in {record['id']}")
        expected_hash = hashlib.sha256(
            json.dumps(
                {"task": record["task"], "input": record["input"], "philosophy": record["philosophy"]},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        check(record["audit"]["content_hash"] == expected_hash, f"bad content hash in {record['id']}")
        group_splits[record["audit"]["group_id"]].add(record["split"])

        image_path = record["input"]["image"].get("path")
        if image_path:
            local_image_count += 1
            path = (ROOT / image_path).resolve()
            check(ROOT.resolve() in path.parents, f"image path escapes repository in {record['id']}")
            check(path.is_file() and valid_image_signature(path), f"missing or invalid image in {record['id']}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            check(record["audit"].get("image_content_sha256") == digest, f"image hash mismatch in {record['id']}")
            image_hash_splits[digest].add(record["split"])

        family = record["task"]["family"]
        answer = record["target"]["answer"]
        if record["task"]["output_type"] == "choice":
            check(answer in set("ABCDEFG"), f"invalid choice answer in {record['id']}")
        if family == "philosophical_aesthetics_dimension_identification":
            evidence = record["philosophy"]["validation"]["evidence"]
            check(answer == "；".join(evidence), f"VULCA target/evidence mismatch in {record['id']}")
            check(all("_L5_" in label for label in evidence), f"non-L5 VULCA label in {record['id']}")
        if record["source"]["benchmark"] == "MM-MoralBench":
            check("unavailable" not in json.dumps(record["input"]["context"]).lower(), f"stale MM context in {record['id']}")

    check(all(len(splits) == 1 for splits in group_splits.values()), "a source/content group crosses splits")
    check(all(len(splits) == 1 for splits in image_hash_splits.values()), "duplicate image content crosses splits")
    check(local_image_count == 1912, "local image count must be 1,912")
    check(card["version"] == VERSION and card["record_count"] == 2800, "dataset card metadata is stale")
    check(all(card["quality_checks"].values()), "dataset card reports failed checks")
    check("�" not in json.dumps(records, ensure_ascii=False), "Unicode replacement character found")

    print(json.dumps({
        "status": "passed",
        "version": VERSION,
        "records": len(records),
        "local_images": local_image_count,
        "unique_image_content": len(image_hash_splits),
        "splits": {name: len(rows) for name, rows in split_rows.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
