from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path


OUT = Path(__file__).resolve().parents[1]
PROJECT = OUT.parent
RELEASE_VERSION = "3000-image-rich-v5"
RELEASE_DATE = "2026-09-03"
BASE = PROJECT / "Philosophical_Multimodal_Benchmark_2800"
BASE_RECORDS = BASE / "data" / "benchmark.jsonl"
SOURCE_DIR = PROJECT / "outputs" / "philosophical_benchmark_merge_5000_20260902"
SOURCE_CSV = SOURCE_DIR / "philosophical_examples_5000.csv"
SOURCE_JSONL = SOURCE_DIR / "philosophical_examples_5000.jsonl"
SOURCE_BUILDER = SOURCE_DIR / "build_expanded_merge.py"
MM_IMAGE_ARCHIVE = Path(os.environ.get("MM_MORAL_IMAGE_ARCHIVE", str(Path.home() / "Downloads" / "M3oral_images.zip")))
RESOURCE_ROOT = PROJECT / "Benchmark_Resources_repo" / "research_benchmarks"
MM_QUERY_FILE = RESOURCE_ROOT / "MM-MoralBench" / "repository" / "query.json"

SOURCE_ORDER = {"HL Dataset": 0, "HSSBench": 1, "MM-MoralBench": 2, "VULCA-Bench": 3}
MM_TASK_QUOTAS = {"moral_judge": 140, "moral_classification": 70, "moral_response": 70}
MM_TASK_FAMILIES = {"judge": "moral_judge", "classification": "moral_classification", "response": "moral_response"}
MM_THEMES = {
    "Care": "伦理学：关怀与伤害",
    "Fairness": "伦理学：公平与正义",
    "Loyalty": "社群伦理：忠诚与背叛",
    "Authority": "政治伦理：权威、义务与服从",
    "Sanctity": "道德心理：神圣与纯洁",
    "Liberty": "政治哲学：自由与压迫",
}
HL_THEME_QUOTAS = {
    "伦理学：关怀、伤害与责任": 156,
    "美学：艺术、创造与表达": 142,
    "认识论：学习、知识与理解": 329,
    "生命哲学：死亡、苦难与生存": 14,
    "政治哲学：正义、权利与自由": 63,
    "宗教哲学：信仰、仪式与超越": 25,
}
VULCA_CULTURE_QUOTAS = {
    "chinese": 71,
    "western": 126,
    "japanese": 48,
    "korean": 30,
    "indian": 25,
    "islamic": 28,
    "hermitage": 37,
    "mural": 44,
}


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalized_prompt(record: dict) -> str:
    text = record["input"]["prompt"].get("en") or record["input"]["prompt"].get("zh") or ""
    return "".join(character.lower() for character in text if character.isalnum())


def priority(record: dict) -> tuple:
    core = 0 if record["audit"].get("previous_selection_tier", "").startswith("核心") else 1
    return core, stable_hash(record["source"]["original_id"])


def parse_json_or_text(value: str):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def load_hl_patterns():
    spec = importlib.util.spec_from_file_location("expanded_merge", SOURCE_BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module.base.HL_CURATED_PATTERNS


def make_hl_record(row: dict, raw: dict, pattern, previous_id: str | None) -> dict:
    matched = [
        {"axis": axis, "text": text}
        for axis in ("scene", "action", "rationale")
        for text in raw["official"]["captions"][axis]
        if pattern.search(text)
    ]
    support = len(matched)
    quality = float(row["source_quality_score"])
    strict = support >= 2 and quality >= 3.5
    if not strict:
        assert support == 1 and quality >= 4.5 and matched[0]["axis"] in {"action", "rationale"}
    authority = "strict_rule_plus_official_confidence" if strict else "image_enrichment_action_rationale_evidence"
    criterion = (
        "同一哲学主题在高层场景/行动/理由标注中至少命中2次，且官方平均置信度不低于3.5"
        if strict
        else "行动或理由高层标注中至少有1条直接哲学主题证据，且官方平均置信度不低于4.5；仅场景词命中不纳入"
    )
    group_key = f"HL Dataset|{row['image_original_reference'] or row['source_id']}"
    return {
        "id": previous_id or f"HL-TEMP-{row['source_id']}",
        "split": "train",
        "task": {"family": "scene_action_rationale", "output_type": "free_text_rationale"},
        "input": {
            "prompt": {"zh": row["prompt_zh"] or None, "en": row["prompt_en"] or None},
            "context": {"zh": parse_json_or_text(row["context_zh"]), "en": parse_json_or_text(row["context_en"])},
            "options": None,
            "image": {
                "path": row["image_local_path"],
                "original_reference": row["image_original_reference"],
                "availability": "本地原始图像可用（路径相对项目根目录）",
            },
        },
        "target": {"answer": row["reference_answer"], "type": "free_text_rationale"},
        "philosophy": {
            "primary_theme": row["philosophical_theme"],
            "secondary_themes": [value for value in row["secondary_themes"].split("；") if value],
            "validation": {
                "status": "passed",
                "authority": authority,
                "criterion": criterion,
                "evidence_count": support,
                "evidence": matched,
                "quality_score": quality,
            },
        },
        "source": {
            "benchmark": "HL Dataset",
            "original_id": row["source_id"],
            "original_split": row["source_split"],
            "url": row["source_url"],
            "category": row["category"],
            "license_or_rights_note": row["license_or_rights_note"],
        },
        "audit": {
            "selected_from": "philosophical_examples_5000",
            "previous_selection_tier": row["selection_tier"],
            "group_id": stable_hash(group_key)[:20],
            "philosophy_pass": True,
            "selection_version": RELEASE_VERSION,
            "hl_selection_tier": "strict" if strict else "image_enrichment",
        },
    }


def make_mm_record(item: dict, previous: dict | None) -> dict:
    if previous:
        return deepcopy(previous)
    family = MM_TASK_FAMILIES[item["type"]]
    foundation = item["Foundation"]
    return {
        "id": f"MM-TEMP-{item['id']}",
        "split": "train",
        "task": {"family": family, "output_type": "choice"},
        "input": {
            "prompt": {"zh": None, "en": item["instruction"]},
            "context": {"zh": None, "en": None},
            "options": None,
            "image": {
                "path": None,
                "original_reference": item["image"],
                "availability": "将从官方 M3oral_images.zip 校验映射并提取",
            },
        },
        "target": {"answer": item["gt_choice"], "type": "choice"},
        "philosophy": {
            "primary_theme": MM_THEMES[foundation],
            "secondary_themes": [foundation],
            "validation": {
                "status": "passed",
                "authority": "official_moral_foundation_label",
                "criterion": "官方 Moral Foundations Theory 道德基础任务",
                "evidence_count": 1,
                "evidence": [foundation, item["type"]],
                "quality_score": None,
            },
        },
        "source": {
            "benchmark": "MM-MoralBench",
            "original_id": str(item["id"]),
            "original_split": "all",
            "url": "https://github.com/BeiiiY/MM-MoralBench",
            "category": foundation,
            "license_or_rights_note": (
                "Official repository has no standalone LICENSE; images come from the public "
                "M3oral_images.zip archive; confirm redistribution permission before reuse."
            ),
        },
        "audit": {
            "selected_from": "MM-MoralBench official query.json",
            "previous_selection_tier": "官方全集扩展（v5）",
            "group_id": stable_hash(f"MM-MoralBench|{item['image']}")[:20],
            "philosophy_pass": True,
            "selection_version": RELEASE_VERSION,
        },
    }


def make_mm_source_snapshot(item: dict) -> dict:
    return {
        "merged_id": f"MM-MoralBench::{item['id']}",
        "source_benchmark": "MM-MoralBench",
        "source_split": "all",
        "source_id": str(item["id"]),
        "philosophical_theme": MM_THEMES[item["Foundation"]],
        "secondary_themes": item["Foundation"],
        "task_type": item["type"],
        "category": item["Foundation"],
        "prompt_en": item["instruction"],
        "reference_answer": item["gt_choice"],
        "image_original_reference": item["image"],
        "source_url": "https://github.com/BeiiiY/MM-MoralBench",
    }


def select_records(records: list[dict], source_rows: list[dict], raw_by_merged_id: dict[str, dict], mm_source_records: list[dict]) -> tuple[list[dict], dict]:
    patterns = load_hl_patterns()
    previous_ids = {
        (record["source"]["benchmark"], record["source"]["original_id"]): record["id"]
        for record in records
    }
    hl = []
    hl_audit = {}
    for theme, quota in HL_THEME_QUOTAS.items():
        rows = [row for row in source_rows if row["source_benchmark"] == "HL Dataset" and row["philosophical_theme"] == theme]
        strict = [row for row in rows if int(row["theme_support_count"]) >= 2 and float(row["source_quality_score"]) >= 3.5]
        enrichment = []
        for row in rows:
            if int(row["theme_support_count"]) != 1 or float(row["source_quality_score"]) < 4.5:
                continue
            raw = raw_by_merged_id[row["merged_id"]]
            pattern = patterns[theme]
            matched_axes = {
                axis
                for axis in ("action", "rationale")
                for text in raw["official"]["captions"][axis]
                if pattern.search(text)
            }
            if matched_axes:
                enrichment.append(row)
        strict.sort(key=lambda row: (-float(row["source_quality_score"]), stable_hash(row["merged_id"])))
        enrichment.sort(key=lambda row: (-float(row["source_quality_score"]), stable_hash(row["merged_id"])))
        assert len(strict) <= quota <= len(strict) + len(enrichment), (theme, len(strict), len(enrichment), quota)
        chosen = strict + enrichment[: quota - len(strict)]
        hl_audit[theme] = {"strict": len(strict), "image_enrichment": quota - len(strict), "selected": quota}
        for row in chosen:
            raw = raw_by_merged_id[row["merged_id"]]
            previous_id = previous_ids.get(("HL Dataset", row["source_id"]))
            hl.append(make_hl_record(row, raw, patterns[theme], previous_id))
    assert len(hl) == 729

    hss = [record for record in records if record["source"]["benchmark"] == "HSSBench"]
    assert len(hss) == 182
    assert len({normalized_prompt(record) for record in hss}) == 182

    previous_mm = {
        record["source"]["original_id"]: record
        for record in records
        if record["source"]["benchmark"] == "MM-MoralBench"
    }
    mm = []
    for foundation in MM_THEMES:
        for raw_task, family in MM_TASK_FAMILIES.items():
            quota = MM_TASK_QUOTAS[family]
            pool = [item for item in mm_source_records if item["Foundation"] == foundation and item["type"] == raw_task]
            pool.sort(key=lambda item: (0 if str(item["id"]) in previous_mm else 1, stable_hash(str(item["id"]))))
            assert len(pool) >= quota, (foundation, raw_task, len(pool), quota)
            mm.extend(make_mm_record(item, previous_mm.get(str(item["id"]))) for item in pool[:quota])
    assert len(mm) == 1680
    assert set(previous_mm).issubset({record["source"]["original_id"] for record in mm})

    vulca = []
    for culture, quota in VULCA_CULTURE_QUOTAS.items():
        pool = [
            record for record in records
            if record["source"]["benchmark"] == "VULCA-Bench"
            and record["source"]["original_split"] == culture
            and float(record["philosophy"]["validation"]["quality_score"]) >= 85
        ]
        assert len(pool) >= quota, (culture, len(pool), quota)
        themes = defaultdict(list)
        for record in pool:
            themes[record["philosophy"]["primary_theme"]].append(record)
        for theme_records in themes.values():
            theme_records.sort(key=lambda record: (priority(record), -float(record["philosophy"]["validation"]["quality_score"])))
        chosen = []
        while len(chosen) < quota:
            progressed = False
            for theme in sorted(themes):
                if themes[theme]:
                    chosen.append(themes[theme].pop(0))
                    progressed = True
                    if len(chosen) == quota:
                        break
            if not progressed:
                raise RuntimeError(f"VULCA pool exhausted for {culture}")
        vulca.extend(chosen)
    assert len(vulca) == 409

    selected = hl + hss + mm + vulca
    assert len(selected) == 3000
    assert len({(record["source"]["benchmark"], record["source"]["original_id"]) for record in selected}) == 3000
    audit = {
        "hl_theme_tiers": hl_audit,
        "hss_conflict_deduplication_inherited_from": "2800-refined-v2",
        "mm_previous_release_records_retained": len(previous_mm),
    }
    return selected, audit


def stratum(record: dict) -> str:
    source = record["source"]["benchmark"]
    if source == "MM-MoralBench":
        return f"{source}|{record['source']['category']}|{record['task']['family']}"
    if source == "VULCA-Bench":
        return f"{source}|{record['source']['original_split']}|{record['philosophy']['primary_theme']}"
    return f"{source}|{record['philosophy']['primary_theme']}"


def sha256_stream(handle) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def assign_content_group_ids(records: list[dict]) -> dict:
    hashes = Counter()
    assert MM_IMAGE_ARCHIVE.exists(), MM_IMAGE_ARCHIVE
    with zipfile.ZipFile(MM_IMAGE_ARCHIVE) as archive:
        members = set(archive.namelist())
        for record in records:
            source = record["source"]["benchmark"]
            digest = None
            if source == "HL Dataset":
                path = PROJECT / record["input"]["image"]["path"]
                with path.open("rb") as handle:
                    digest = sha256_stream(handle)
            elif source == "HSSBench":
                path = BASE / record["input"]["image"]["path"]
                with path.open("rb") as handle:
                    digest = sha256_stream(handle)
            elif source == "MM-MoralBench":
                member = record["input"]["image"]["original_reference"].replace("\\", "/").lstrip("./")
                assert member in members, member
                with archive.open(member) as handle:
                    digest = sha256_stream(handle)
            if digest:
                record["audit"]["image_content_sha256"] = digest
                record["audit"]["group_id"] = digest[:20]
                hashes[digest] += 1
    return {
        "local_image_hash_count": sum(hashes.values()),
        "unique_local_image_content_count": len(hashes),
        "duplicate_image_content_group_count": sum(count > 1 for count in hashes.values()),
        "records_in_duplicate_image_groups": sum(count for count in hashes.values() if count > 1),
    }


def assign_splits(records: list[dict]) -> dict[tuple[str, str], str]:
    groups = defaultdict(list)
    for record in records:
        groups[stratum(record)].append(record)
    assignments = {}
    for items in groups.values():
        items.sort(key=lambda record: stable_hash(record["source"]["benchmark"] + "|" + record["source"]["original_id"] + "|split-v3"))
        count = len(items)
        dev = max(1, round(count * 0.1)) if count >= 3 else 0
        test = max(1, round(count * 0.1)) if count >= 3 else (1 if count == 2 else 0)
        train = count - dev - test
        for index, record in enumerate(items):
            key = (record["source"]["benchmark"], record["source"]["original_id"])
            assignments[key] = "train" if index < train else "dev" if index < train + dev else "test"
    content_groups = defaultdict(list)
    for record in records:
        content_groups[record["audit"]["group_id"]].append(record)
    for group_id, items in content_groups.items():
        if len(items) < 2:
            continue
        bucket = int(stable_hash(group_id + "|image-group-split-v3")[:8], 16) % 10
        split = "train" if bucket < 8 else "dev" if bucket == 8 else "test"
        for record in items:
            key = (record["source"]["benchmark"], record["source"]["original_id"])
            assignments[key] = split
    return assignments


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def prepare_records(selected: list[dict], assignments: dict[tuple[str, str], str]) -> list[dict]:
    selected.sort(key=lambda record: (
        SOURCE_ORDER[record["source"]["benchmark"]],
        record["source"]["original_split"],
        record["source"]["original_id"],
    ))
    prepared = []
    assert MM_IMAGE_ARCHIVE.exists(), MM_IMAGE_ARCHIVE
    with zipfile.ZipFile(MM_IMAGE_ARCHIVE) as archive:
        archive_members = set(archive.namelist())
        assert len([name for name in archive_members if name.lower().endswith(".jpg")]) == 4640
        for index, original in enumerate(selected, start=1):
            record = deepcopy(original)
            old_id = record["id"]
            record_id = f"PHILBENCH-3000-{index:04d}"
            source = record["source"]["benchmark"]
            key = (source, record["source"]["original_id"])
            record["id"] = record_id
            record["split"] = assignments[key]

            if source == "HL Dataset":
                source_image = PROJECT / record["input"]["image"]["path"]
                assert source_image.exists(), source_image
                destination = OUT / "images" / "HL_Dataset" / f"{record_id}{source_image.suffix.lower()}"
                link_or_copy(source_image, destination)
                record["input"]["image"]["path"] = destination.relative_to(OUT).as_posix()
            elif source == "HSSBench":
                source_image = BASE / record["input"]["image"]["path"]
                assert source_image.exists(), source_image
                destination = OUT / "images" / "HSSBench" / f"{record_id}{source_image.suffix.lower()}"
                link_or_copy(source_image, destination)
                record["input"]["image"]["path"] = destination.relative_to(OUT).as_posix()
            elif source == "MM-MoralBench":
                member = record["input"]["image"]["original_reference"].replace("\\", "/").lstrip("./")
                assert member in archive_members, member
                destination = OUT / "images" / "MM-MoralBench" / f"{record_id}.jpg"
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source_handle, destination.open("wb") as destination_handle:
                    shutil.copyfileobj(source_handle, destination_handle)
                record["input"]["image"]["path"] = destination.relative_to(OUT).as_posix()
                record["input"]["image"]["availability"] = "本地图像已从官方 M3oral_images.zip 校验映射并提取"
                record["input"]["context"] = {"zh": None, "en": None}
                record["source"]["license_or_rights_note"] = (
                    "Official repository has no standalone LICENSE; images come from the public "
                    "M3oral_images.zip archive; confirm redistribution permission before reuse."
                )

            if source == "VULCA-Bench":
                record["philosophy"]["validation"]["criterion"] = "官方 L5 Philosophical Aesthetics 维度且质量分不低于85"
                record["target"]["answer"] = "；".join(record["philosophy"]["validation"]["evidence"])

            record["audit"]["derived_from_record_id"] = old_id if old_id.startswith("PHILBENCH-") else None
            record["audit"]["selection_version"] = RELEASE_VERSION
            query_basis = json.dumps(
                {"task": record["task"], "input": record["input"], "philosophy": record["philosophy"]},
                ensure_ascii=False,
                sort_keys=True,
            )
            record["audit"]["content_hash"] = stable_hash(query_basis)
            prepared.append(record)

    counts = Counter((record["source"]["benchmark"], normalized_prompt(record)) for record in prepared)
    for record in prepared:
        record["audit"]["same_prompt_count_within_source"] = counts[(record["source"]["benchmark"], normalized_prompt(record))]
    return prepared


def flatten(record: dict) -> dict:
    validation = record["philosophy"]["validation"]
    image = record["input"]["image"]
    return {
        "id": record["id"],
        "split": record["split"],
        "source_benchmark": record["source"]["benchmark"],
        "source_id": record["source"]["original_id"],
        "source_split_or_culture": record["source"]["original_split"],
        "task_family": record["task"]["family"],
        "output_type": record["task"]["output_type"],
        "primary_theme": record["philosophy"]["primary_theme"],
        "secondary_themes": "；".join(record["philosophy"]["secondary_themes"]),
        "prompt_zh": record["input"]["prompt"].get("zh") or "",
        "prompt_en": record["input"]["prompt"].get("en") or "",
        "context_zh": json.dumps(record["input"]["context"].get("zh"), ensure_ascii=False) if record["input"]["context"].get("zh") is not None else "",
        "context_en": json.dumps(record["input"]["context"].get("en"), ensure_ascii=False) if record["input"]["context"].get("en") is not None else "",
        "options": json.dumps(record["input"]["options"], ensure_ascii=False) if record["input"]["options"] else "",
        "answer": record["target"]["answer"],
        "image_path": image.get("path") or "",
        "image_local_available": bool(image.get("path")),
        "image_original_reference": image.get("original_reference") or "",
        "image_availability": image.get("availability") or "",
        "philosophy_authority": validation["authority"],
        "philosophy_criterion": validation["criterion"],
        "evidence_count": validation["evidence_count"],
        "evidence_axes": "；".join(sorted({item["axis"] for item in validation["evidence"] if isinstance(item, dict) and "axis" in item})),
        "quality_score": validation["quality_score"] if validation["quality_score"] is not None else "",
        "hl_selection_tier": record["audit"].get("hl_selection_tier", ""),
        "previous_selection_tier": record["audit"].get("previous_selection_tier", ""),
        "derived_from_record_id": record["audit"].get("derived_from_record_id", ""),
        "source_url": record["source"]["url"],
        "rights_note": record["source"]["license_or_rights_note"],
        "content_hash": record["audit"]["content_hash"],
    }


def build_query(record: dict) -> dict:
    """构造盲测输入：仅保留作答所需字段，剔除可泄漏答案的元数据。

    泄漏源：philosophy.primary_theme / source.category 直接等于部分任务（如
    MM-MoralBench 的 moral_classification）的正确答案；audit 含内部选择痕迹。
    因此盲测 query 只保留 id/split/task/input。
    original_reference 对全部记录无条件移除（v5.1 修复）：本地图片的原始文件名
    可映射到上游来源；VULCA 等无图记录的原始引用更直接包含作品名、作者与内容
    标签，属于答案线索，必须无条件剔除，无论 image.path 是否存在。
    """
    image = dict(record["input"]["image"])
    image.pop("original_reference", None)
    return {
        "id": record["id"],
        "split": record["split"],
        "task": record["task"],
        "input": {**record["input"], "image": image},
    }


def reset_output_dirs() -> None:
    for name in ("data", "splits", "images", "source_snapshots", "references"):
        target = OUT / name
        assert target.parent == OUT and target.name == name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
    review = OUT / "review"
    review.mkdir(parents=True, exist_ok=True)
    for filename in (
        "philosophical_multimodal_benchmark_2800_image_rich.csv",
        "philosophical_multimodal_benchmark_3000_image_rich.csv",
    ):
        generated_csv = review / filename
        if generated_csv.exists():
            generated_csv.unlink()


def write_source_snapshots(records: list[dict], mm_source_records: list[dict]) -> None:
    wanted = {(record["source"]["benchmark"], record["source"]["original_id"]): record["id"] for record in records}
    source_records = {}
    with SOURCE_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            unified = item["unified"]
            key = (unified["source_benchmark"], unified["source_id"])
            source_records[key] = (unified, item["raw_source_record"])
    for item in mm_source_records:
        key = ("MM-MoralBench", str(item["id"]))
        source_records.setdefault(key, (make_mm_source_snapshot(item), item))
    snapshots = []
    for key, record_id in wanted.items():
        assert key in source_records, key
        unified, raw = source_records[key]
        snapshots.append({
            "id": record_id,
            "source_benchmark": key[0],
            "source_id": key[1],
            "unified_source_record": unified,
            "raw_source_record": raw,
        })
    assert len(snapshots) == 3000
    snapshots.sort(key=lambda item: item["id"])
    write_jsonl(OUT / "source_snapshots" / "selected_source_records.jsonl", snapshots)


def copy_references() -> list[dict]:
    files = [
        (PROJECT / "hl_dataset_official" / "README.md", "HL_Dataset/README_official.md"),
        (PROJECT / "hl_dataset_official" / "LICENSE", "HL_Dataset/LICENSE"),
        (RESOURCE_ROOT / "_summary" / "benchmark_papers.bib", "benchmark_papers.bib"),
        (RESOURCE_ROOT / "HSSBench" / "README_CN.md", "HSSBench/README_CN.md"),
        (RESOURCE_ROOT / "HSSBench" / "repository" / "README.md", "HSSBench/README_official.md"),
        (RESOURCE_ROOT / "HSSBench" / "papers" / "HSSBench_arXiv_2506.03922.pdf", "HSSBench/HSSBench_arXiv_2506.03922.pdf"),
        (RESOURCE_ROOT / "MM-MoralBench" / "repository" / "README.md", "MM-MoralBench/README_official.md"),
        (RESOURCE_ROOT / "MM-MoralBench" / "papers" / "MM-MoralBench_arXiv_2412.20718.pdf", "MM-MoralBench/MM-MoralBench_arXiv_2412.20718.pdf"),
        (RESOURCE_ROOT / "ValueGround" / "README_CN.md", "ValueGround/README_CN.md"),
        (RESOURCE_ROOT / "ValueGround" / "repository" / "README.md", "ValueGround/README_official.md"),
        (RESOURCE_ROOT / "ValueGround" / "papers" / "ValueGround_arXiv_2604.06484.pdf", "ValueGround/ValueGround_arXiv_2604.06484.pdf"),
        (RESOURCE_ROOT / "VULCA-Bench" / "README_CN.md", "VULCA-Bench/README_CN.md"),
        (RESOURCE_ROOT / "VULCA-Bench" / "repository" / "README.md", "VULCA-Bench/README_official.md"),
        (RESOURCE_ROOT / "VULCA-Bench" / "repository" / "LICENSE", "VULCA-Bench/LICENSE"),
        (RESOURCE_ROOT / "VULCA-Bench" / "repository" / "IMAGE_RIGHTS.md", "VULCA-Bench/IMAGE_RIGHTS.md"),
        (RESOURCE_ROOT / "VULCA-Bench" / "repository" / "RELEASES.md", "VULCA-Bench/RELEASES.md"),
        (RESOURCE_ROOT / "VULCA-Bench" / "repository" / "data" / "license_rights_manifest_v2_1.csv", "VULCA-Bench/license_rights_manifest_v2_1.csv"),
        (RESOURCE_ROOT / "VULCA-Bench" / "repository" / "release" / "v2.1" / "manifest.json", "VULCA-Bench/release_manifest_v2_1.json"),
        (RESOURCE_ROOT / "VULCA-Bench" / "papers" / "VULCA-Bench_arXiv_2601.07986.pdf", "VULCA-Bench/VULCA-Bench_arXiv_2601.07986.pdf"),
    ]
    manifest = []
    for source, relative in files:
        assert source.exists(), source
        destination = OUT / "references" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest.append({
            "path": destination.relative_to(OUT).as_posix(),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "size_bytes": destination.stat().st_size,
        })
    links = {
        "HL Dataset": {"github": "https://github.com/michelecafagna26/HL-dataset", "selected_records": 729, "local_selected_images": 729},
        "HSSBench": {"github": "https://github.com/Zhaolu-K/HSSBench", "paper": "https://arxiv.org/abs/2506.03922", "selected_records": 182},
        "MM-MoralBench": {"github": "https://github.com/BeiiiY/MM-MoralBench", "paper": "https://arxiv.org/abs/2412.20718", "image_download": "https://1drv.ms/u/c/3990e975c588b26f/EYe5aG7eOhhIq4rUxdErgyoBHZBH6kBeKa-q0gRzMMq7Rg", "selected_records": 1680, "local_selected_images": 1680, "archive_file_name": "M3oral_images.zip", "archive_size_bytes": MM_IMAGE_ARCHIVE.stat().st_size},
        "ValueGround": {"github": "https://github.com/NL2G/ValueGround", "paper": "https://arxiv.org/abs/2604.06484", "selected_records": 0, "status": "论文与方法参考；截至2026-09-01官方数据尚未发布"},
        "VULCA-Bench": {"github": "https://github.com/vulca-org/vulca-cultural-visual-benchmark", "paper": "https://arxiv.org/abs/2601.07986", "selected_records": 409, "image_status": "第三方艺术图像不再分发"},
    }
    payload = {"files": manifest, "official_links": links}
    (OUT / "references" / "reference_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate(records: list[dict], queries: list[dict], answers: list[dict]) -> dict[str, bool]:
    ids = [record["id"] for record in records]
    group_splits = defaultdict(set)
    for record in records:
        group_splits[record["audit"]["group_id"]].add(record["split"])
    hss_prompts = [normalized_prompt(record) for record in records if record["source"]["benchmark"] == "HSSBench"]
    image_records = [record for record in records if record["input"]["image"]["path"]]
    image_hash_groups = defaultdict(list)
    for record in image_records:
        image_hash_groups[record["audit"]["image_content_sha256"]].append(record)
    duplicate_image_groups = [items for items in image_hash_groups.values() if len(items) > 1]
    def valid_image_signature(record: dict) -> bool:
        header = (OUT / record["input"]["image"]["path"]).read_bytes()[:12]
        return header.startswith(b"\xff\xd8\xff") or header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"GIF8") or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
    return {
        "row_count_is_3000": len(records) == 3000,
        "ids_unique": len(ids) == len(set(ids)) == 3000,
        "source_distribution_exact": Counter(record["source"]["benchmark"] for record in records) == Counter({"HL Dataset": 729, "HSSBench": 182, "MM-MoralBench": 1680, "VULCA-Bench": 409}),
        "all_philosophy_checks_pass": all(record["audit"]["philosophy_pass"] and record["philosophy"]["validation"]["status"] == "passed" for record in records),
        "hl_strict_tier_valid": all(record["philosophy"]["validation"]["evidence_count"] >= 2 and record["philosophy"]["validation"]["quality_score"] >= 3.5 for record in records if record["source"]["benchmark"] == "HL Dataset" and record["audit"].get("hl_selection_tier") == "strict"),
        "hl_image_enrichment_tier_valid": all(record["philosophy"]["validation"]["evidence_count"] == 1 and record["philosophy"]["validation"]["quality_score"] >= 4.5 and record["philosophy"]["validation"]["evidence"][0]["axis"] in {"action", "rationale"} for record in records if record["source"]["benchmark"] == "HL Dataset" and record["audit"].get("hl_selection_tier") == "image_enrichment"),
        "hl_tiers_cover_all_729": Counter(record["audit"].get("hl_selection_tier") for record in records if record["source"]["benchmark"] == "HL Dataset") == Counter({"strict": 237, "image_enrichment": 492}),
        "hss_normalized_prompts_unique": len(hss_prompts) == len(set(hss_prompts)),
        "mm_quota_exact": all(sum(1 for record in records if record["source"]["benchmark"] == "MM-MoralBench" and record["source"]["category"] == foundation and record["task"]["family"] == task) == quota for foundation in ("Care", "Fairness", "Loyalty", "Authority", "Sanctity", "Liberty") for task, quota in MM_TASK_QUOTAS.items()),
        "mm_choice_labels_complete": all(
            {record["target"]["answer"] for record in records if record["source"]["benchmark"] == "MM-MoralBench" and record["task"]["family"] == task} == labels
            for task, labels in {
                "moral_judge": {"A", "B"},
                "moral_classification": {"A", "B", "C", "D", "E", "F", "G"},
                "moral_response": {"A", "B"},
            }.items()
        ),
        "vulca_l5_and_quality_ge_85": all(record["philosophy"]["validation"]["evidence_count"] >= 1 and record["philosophy"]["validation"]["quality_score"] >= 85 for record in records if record["source"]["benchmark"] == "VULCA-Bench"),
        "vulca_culture_quota_exact": all(sum(1 for record in records if record["source"]["benchmark"] == "VULCA-Bench" and record["source"]["original_split"] == culture) == quota for culture, quota in VULCA_CULTURE_QUOTAS.items()),
        "all_local_image_paths_exist": all((OUT / record["input"]["image"]["path"]).exists() for record in records if record["input"]["image"]["path"]),
        "local_image_count_is_2591": len(image_records) == 2591,
        "local_image_coverage_exceeds_80_percent": len(image_records) / len(records) > 0.80,
        "image_source_distribution_exact": Counter(record["source"]["benchmark"] for record in image_records) == Counter({"HL Dataset": 729, "HSSBench": 182, "MM-MoralBench": 1680}),
        "all_local_images_have_valid_signatures": all(valid_image_signature(record) for record in image_records),
        "duplicate_image_groups_identified": all(
            record["audit"]["group_id"] == digest[:20]
            for digest, items in image_hash_groups.items()
            for record in items
        ),
        "no_duplicate_image_content_crosses_splits": all(len({record["split"] for record in items}) == 1 for items in duplicate_image_groups),
        "no_group_crosses_splits": all(len(splits) == 1 for splits in group_splits.values()),
        "query_has_no_target_field": all("target" not in query for query in queries),
        "query_contains_only_inference_fields": all(set(query) == {"id", "split", "task", "input"} for query in queries),
        "query_hides_local_source_filenames": all(
            "original_reference" not in query["input"]["image"]
            for query in queries
        ),
        "queries_match_release_records": queries == [build_query(record) for record in records],
        "answer_key_matches_records": answers == [
            {"id": record["id"], "split": record["split"], "target": record["target"]}
            for record in records
        ],
        "content_hashes_unique": len({record["audit"]["content_hash"] for record in records}) == len(records),
        "targets_nonempty": all(str(record["target"]["answer"]).strip() for record in records),
        "vulca_targets_are_l5_only": all(
            record["target"]["answer"] == "；".join(record["philosophy"]["validation"]["evidence"])
            and all("_L5_" in label for label in record["target"]["answer"].split("；"))
            for record in records
            if record["source"]["benchmark"] == "VULCA-Bench"
        ),
        "vulca_labels_removed_from_input": all(not any(label in json.dumps(record["input"], ensure_ascii=False) for label in record["philosophy"]["validation"]["evidence"]) for record in records if record["source"]["benchmark"] == "VULCA-Bench"),
        "mm_context_does_not_claim_images_are_missing": all(
            "unavailable" not in json.dumps(record["input"]["context"], ensure_ascii=False).lower()
            for record in records
            if record["source"]["benchmark"] == "MM-MoralBench"
        ),
        "no_unicode_replacement_character": all("�" not in json.dumps(record, ensure_ascii=False) for record in records),
    }


def main() -> None:
    reset_output_dirs()
    base_records = read_jsonl(BASE_RECORDS)
    assert len(base_records) == 2800
    mm_source_records = json.loads(MM_QUERY_FILE.read_text(encoding="utf-8"))
    assert len(mm_source_records) == 4640
    with SOURCE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    raw_by_merged_id = {}
    for item in read_jsonl(SOURCE_JSONL):
        raw_by_merged_id[item["unified"]["merged_id"]] = item["raw_source_record"]
    assert len(source_rows) == len(raw_by_merged_id) == 5000
    selected, selection_audit = select_records(base_records, source_rows, raw_by_merged_id, mm_source_records)
    image_content_audit = assign_content_group_ids(selected)
    selection_audit["image_content_audit"] = image_content_audit
    assignments = assign_splits(selected)
    records = prepare_records(selected, assignments)

    write_jsonl(OUT / "data" / "benchmark.jsonl", records)
    queries = [build_query(record) for record in records]
    answers = [{"id": record["id"], "split": record["split"], "target": record["target"]} for record in records]
    (OUT / "data" / "query.json").write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "data" / "answer_key.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
    for split in ("train", "dev", "test"):
        write_jsonl(OUT / "splits" / f"{split}.jsonl", [record for record in records if record["split"] == split])

    flat = [flatten(record) for record in records]
    with (OUT / "review" / "philosophical_multimodal_benchmark_3000_image_rich.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)

    write_source_snapshots(records, mm_source_records)
    reference_files = copy_references()

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Philosophical Multimodal Benchmark 3000 Record",
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "split", "task", "input", "target", "philosophy", "source", "audit"],
        "properties": {
            "id": {"type": "string", "pattern": "^PHILBENCH-3000-[0-9]{4}$"},
            "split": {"enum": ["train", "dev", "test"]},
            "task": {
                "type": "object",
                "additionalProperties": False,
                "required": ["family", "output_type"],
                "properties": {
                    "family": {"type": "string", "minLength": 1},
                    "output_type": {"enum": ["choice", "dimension_labels", "free_text_rationale"]},
                },
            },
            "input": {
                "type": "object",
                "additionalProperties": False,
                "required": ["prompt", "context", "options", "image"],
                "properties": {
                    "prompt": {"type": "object", "minProperties": 1},
                    "context": {"type": "object", "required": ["zh", "en"]},
                    "options": {"type": ["object", "null"]},
                    "image": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["path", "original_reference", "availability"],
                        "properties": {
                            "path": {"type": ["string", "null"]},
                            "original_reference": {"type": ["string", "null"]},
                            "availability": {"type": "string"},
                        },
                    },
                },
            },
            "target": {
                "type": "object",
                "additionalProperties": False,
                "required": ["answer", "type"],
                "properties": {
                    "answer": {"type": "string", "minLength": 1},
                    "type": {"enum": ["choice", "dimension_labels", "free_text_rationale"]},
                },
            },
            "philosophy": {
                "type": "object",
                "additionalProperties": False,
                "required": ["primary_theme", "secondary_themes", "validation"],
                "properties": {
                    "primary_theme": {"type": "string", "minLength": 1},
                    "secondary_themes": {"type": "array", "items": {"type": "string"}},
                    "validation": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["status", "authority", "criterion", "evidence_count", "evidence", "quality_score"],
                        "properties": {
                            "status": {"const": "passed"},
                            "authority": {"type": "string", "minLength": 1},
                            "criterion": {"type": "string", "minLength": 1},
                            "evidence_count": {"type": "integer", "minimum": 1},
                            "evidence": {"type": "array", "minItems": 1},
                            "quality_score": {"type": ["number", "null"]},
                        },
                    },
                },
            },
            "source": {
                "type": "object",
                "additionalProperties": False,
                "required": ["benchmark", "original_id", "original_split", "url", "category", "license_or_rights_note"],
                "properties": {
                    "benchmark": {"enum": ["HL Dataset", "HSSBench", "MM-MoralBench", "VULCA-Bench"]},
                    "original_id": {"type": "string", "minLength": 1},
                    "original_split": {"type": "string"},
                    "url": {"type": "string", "pattern": "^https://"},
                    "category": {"type": "string"},
                    "license_or_rights_note": {"type": "string", "minLength": 1},
                },
            },
            "audit": {
                "type": "object",
                "required": ["group_id", "content_hash", "philosophy_pass", "selection_version"],
                "properties": {
                    "group_id": {"type": "string", "minLength": 1},
                    "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "philosophy_pass": {"const": True},
                    "selection_version": {"const": RELEASE_VERSION},
                },
            },
        },
    }
    (OUT / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = validate(records, queries, answers)
    card = {
        "name": "Philosophical Multimodal Benchmark 3000 Image-Rich",
        "version": RELEASE_VERSION,
        "generated_on": RELEASE_DATE,
        "record_count": len(records),
        "source_distribution": Counter(record["source"]["benchmark"] for record in records),
        "split_distribution": Counter(record["split"] for record in records),
        "task_distribution": Counter(record["task"]["family"] for record in records),
        "theme_distribution": Counter(record["philosophy"]["primary_theme"] for record in records),
        "vulca_culture_distribution": Counter(record["source"]["original_split"] for record in records if record["source"]["benchmark"] == "VULCA-Bench"),
        "validation_authority_distribution": Counter(record["philosophy"]["validation"]["authority"] for record in records),
        "local_image_count": sum(bool(record["input"]["image"]["path"]) for record in records),
        "local_image_coverage": round(sum(bool(record["input"]["image"]["path"]) for record in records) / len(records), 6),
        "local_image_distribution": Counter(record["source"]["benchmark"] for record in records if record["input"]["image"]["path"]),
        "image_content_audit": image_content_audit,
        "reference_file_count": len(reference_files),
        "previous_core_overlap": sum(record["audit"].get("previous_selection_tier", "").startswith("核心") for record in records),
        "selection_rules": {
            "HL Dataset": "729 image-bearing records: all records satisfying either the strict tier (support >= 2 and confidence >= 3.5) or image-enrichment tier (exactly one action/rationale match, confidence >= 4.5; scene-only matches excluded)",
            "HSSBench": "official Philosophy/Ethics only; normalized duplicate prompt conflict deduplicated to the prior core/majority-answer record",
            "MM-MoralBench": "280 per moral foundation from the complete official query set: 140 judge, 70 classification, 70 response; all official images locally mapped",
            "VULCA-Bench": "409 official L5 records, quality_score >= 85, culture/theme stratified; artwork images not redistributed",
            "ValueGround": "paper/methodology reference only; no official public data available as of 2026-09-01",
        },
        "selection_audit": selection_audit,
        "known_limitations": [
            "VULCA-Bench records are text-only proxies in this release because third-party artwork images are not redistributed.",
            "HL free-text rationales are scored with a pre-declared lexical proxy (max-reference token F1) implemented in evaluate.py; human or semantic evaluation is still recommended for publication-grade claims.",
            "HL blind queries include the official scene/action/object annotations as input context; models can answer without reading the image, so with-context and no-context conditions should be reported separately.",
            "All records derive from four public upstream benchmarks; training-data contamination cannot be excluded, and users should run memorization or no-image control probes before drawing capability conclusions.",
            "No new inter-annotator agreement statistic is included; HL enrichment labels still require expert audit.",
            "No model baseline results are bundled; evaluate.py defines scoring but does not substitute for experiments.",
            "HSSBench and MM-MoralBench image redistribution permissions should be confirmed before downstream republication.",
        ],
        "quality_checks": checks,
    }
    (OUT / "dataset_card.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    assert all(checks.values()), [name for name, passed in checks.items() if not passed]
    print(json.dumps(card, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
