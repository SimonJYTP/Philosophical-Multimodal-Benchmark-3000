# Philosophical Multimodal Benchmark 3000 — Image-Rich (v5)

这是面向“哲学意味多模态理解”研究的图像增强 benchmark，共 **3,000 条**，其中 **2,591 条具有可直接读取的本地图片，覆盖率 86.37%**。图片均映射自各上游 benchmark 的原始视觉输入，没有用无关图片或合成图片补齐数量。

v5 在 v4 的防泄漏、VULCA L5 目标修复和 MM 图像状态修复基础上，扩展到完整可复现的 3,000 条发布。构建器、独立发布验证器、盲测输入、答案键、来源快照和评分脚本同步升级。

## 1. 数据构成

| 来源 | 条数 | 本地图片 | 图片覆盖率 | 主要用途 |
|---|---:|---:|---:|---|
| HL Dataset | 729 | 729 | 100% | 场景、行动和理由中的责任、认知、审美、宗教及生命处境理解 |
| HSSBench | 182 | 182 | 100% | 官方 Philosophy/Ethics 视觉选择题与多语言推理 |
| MM-MoralBench | 1,680 | 1,680 | 100% | 六类道德基础上的判断、分类和回应 |
| VULCA-Bench | 409 | 0 | 0% | 多文化艺术评论中的 L5 哲学美学维度识别（文本代理任务） |
| ValueGround | 0 | 0 | — | 论文和方法参考；官方数据尚未公开 |
| **合计** | **3,000** | **2,591** | **86.37%** |  |

固定哈希分层划分为 `train` 2,386 条、`dev` 304 条、`test` 310 条。完全相同的图片内容被强制放入同一划分，避免视觉内容泄漏。

## 2. 选择与图像策略

### HL Dataset：729 条

- 严格层 237 条：同一哲学主题在场景/行动/理由标注中至少命中 2 次，官方平均置信度 ≥ 3.5。
- 图像增强层 492 条：行动或理由标注中存在 1 条直接主题证据，官方平均置信度 ≥ 4.5；排除仅场景词命中的候选。
- 六个主题配额：认识论 329、伦理学 156、美学 142、政治哲学 63、宗教哲学 25、生命哲学 14。

`audit.hl_selection_tier`、证据文本、证据轴和质量分均保留，便于分别报告严格层与完整层结果。

### HSSBench：182 条

- 仅保留官方 `Philosophy` 或 `Ethics` 标签记录。
- 前期发现的三条同题、答案 B/C/B 冲突已去重，保留原核心且与多数答案一致的 B 项。
- 规范化后的 182 个题干全部唯一。

### MM-MoralBench：1,680 条

- 使用官方完整 `query.json` 分层选择，而非局限于旧版 1,500 条候选池。
- 六种道德基础各 280 条：Care、Fairness、Loyalty、Authority、Sanctity、Liberty。
- 每种基础包含判断 140、分类 70、回应 70；三类任务总计 840/420/420。
- 旧版的 1,080 条 MM 记录全部保留，新增 600 条按稳定哈希选取。
- 1,680 张图片均从官方 `M3oral_images.zip` 按原始引用校验映射并提取。

### VULCA-Bench：409 条

- 只保留官方 L5 Philosophical Aesthetics 维度且质量分 ≥ 85 的记录。
- 按八种文化传统和哲学主题分层取样。
- 为遵守官方权利边界，不重新分发第三方艺术图片；原始引用和权利材料仍被保留。

## 3. 目录结构

```text
Philosophical_Multimodal_Benchmark_2800_ImageRich/
├─ README.md
├─ dataset_card.json
├─ schema.json
├─ data/
│  ├─ benchmark.jsonl
│  ├─ query.json
│  └─ answer_key.json
├─ splits/
│  ├─ train.jsonl
│  ├─ dev.jsonl
│  └─ test.jsonl
├─ images/
│  ├─ HL_Dataset/                    # 729 张
│  ├─ HSSBench/                      # 182 张
│  └─ MM-MoralBench/                 # 1,680 张
├─ source_snapshots/
│  └─ selected_source_records.jsonl  # 3,000 条原始来源快照
├─ review/
│  └─ philosophical_multimodal_benchmark_3000_image_rich.csv
├─ references/
└─ scripts/
   ├─ build_dataset.py
   ├─ validate_release.py
   └─ evaluate.py
```

仓库目录名为保持 GitHub URL 兼容暂未改名；数据集版本、记录 ID 和发布文件名均已升级为 3000/v5。

## 4. 记录与盲测格式

`data/benchmark.jsonl` 每行是一条完整记录，核心结构如下：

```json
{
  "id": "PHILBENCH-3000-0001",
  "split": "train",
  "task": {"family": "scene_action_rationale", "output_type": "free_text_rationale"},
  "input": {
    "prompt": {"zh": "...", "en": "..."},
    "context": {"zh": null, "en": {}},
    "options": null,
    "image": {
      "path": "images/HL_Dataset/PHILBENCH-3000-0001.png",
      "original_reference": "...",
      "availability": "..."
    }
  },
  "target": {"answer": "...", "type": "free_text_rationale"},
  "philosophy": {"primary_theme": "...", "secondary_themes": [], "validation": {}},
  "source": {"benchmark": "HL Dataset", "original_id": "..."},
  "audit": {"group_id": "...", "content_hash": "...", "selection_version": "3000-image-rich-v5"}
}
```

盲测时只向模型提供 `data/query.json`。该文件顶层严格只含 `id`、`split`、`task`、`input`，并移除了 `target`、答案相关哲学/来源元数据以及本地图像原始文件名。推理完成后用 `data/answer_key.json` 按 ID 对齐评分。

## 5. 快速使用

```python
import json
from pathlib import Path

root = Path(".")
with (root / "data" / "benchmark.jsonl").open(encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

image_records = [r for r in records if r["input"]["image"]["path"]]
assert len(records) == 3000
assert len(image_records) == 2591
assert len(image_records) / len(records) > 0.80
assert (root / image_records[0]["input"]["image"]["path"]).exists()
```

HL 可按证据严格程度拆分：

```python
hl_strict = [r for r in records if r["source"]["benchmark"] == "HL Dataset" and r["audit"].get("hl_selection_tier") == "strict"]
hl_enrichment = [r for r in records if r["source"]["benchmark"] == "HL Dataset" and r["audit"].get("hl_selection_tier") == "image_enrichment"]
assert len(hl_strict) == 237
assert len(hl_enrichment) == 492
```

## 6. 推荐评测指标

| 任务族 | 输出 | 主指标 |
|---|---|---|
| `scene_action_rationale` | 自由文本 Rationale | 人工量表 + 预先声明的语义指标 |
| `visual_multiple_choice_qa` | A–D | Accuracy |
| `moral_judge` | A/B | Accuracy |
| `moral_classification` | A–G | Accuracy |
| `moral_response` | A/B | Accuracy |
| `philosophical_aesthetics_dimension_identification` | L5 标签集合 | Micro-F1、Macro-F1、Exact Match |

对自动评分任务运行：

```powershell
py -3 .\scripts\evaluate.py .\predictions.jsonl --split test
```

脚本要求预测 ID 与所选划分完全一致。HL 自由文本会明确列为需要语义或人工评分，不会用不恰当的字面匹配混入总分。跨来源汇总时应先报告各来源结果，再使用明确归一化的宏平均。

## 7. 构建与验证

构建器依赖 Python 标准库，并默认从用户下载目录读取 `M3oral_images.zip`：

```powershell
$env:MM_MORAL_IMAGE_ARCHIVE='D:\path\to\M3oral_images.zip'  # 非默认位置时设置
py -3 .\scripts\build_dataset.py
py -3 .\scripts\validate_release.py
```

构建脚本会刷新数据、图片、来源快照、CSV、schema 和参考材料。独立验证器不依赖原始源目录，会逐条检查：文件对齐、ID/版本、内容哈希、图片存在性与签名、图片 SHA-256、分组隔离、盲测输入和答案键。

## 8. 质量保证

`dataset_card.json` 中的自动检查覆盖：

- 3,000 条总量、四个来源配额、ID 和内容哈希唯一性；
- HL 两种证据层级、HSS 题干去重、MM 基础×任务配额及答案标签域；
- VULCA L5、质量阈值、文化配额与输入/目标隔离；
- 2,591 个本地图片路径、文件签名和 SHA-256 一致性；
- 2,440 个唯一图像内容、151 个重复内容组、所有重复内容不跨划分；
- 86.37% 图像覆盖率，严格高于 80%；
- 盲测查询不含 target、答案相关元数据或本地图像原始文件名；
- 无 Unicode 替换字符。

自动规则不能替代哲学专家复核。论文定稿前仍建议对 HL 图像增强层进行分层抽样专家复核，报告标注一致性，并实际运行基线模型。

## 9. 图片与许可边界

- HL Dataset：标注采用 Apache-2.0；图像和对象描述仍受 COCO 原始条款约束。
- HSSBench：官方仓库没有独立 LICENSE；公开再分发前应向作者或权利方确认。
- MM-MoralBench：图片来自作者 README 提供的公开图像包，但官方仓库没有独立 LICENSE；公开再分发前需确认许可。
- VULCA-Bench：benchmark 元数据、评论和工具使用 CC BY 4.0；该许可不自动覆盖第三方艺术作品图片。
- ValueGround：仅保存论文和仓库说明，没有虚构未发布数据。

相关论文、官方 README、许可证、VULCA 图像权利说明和逐条权利清单位于 `references/`。仓库不附加一个覆盖全部上游内容的统一数据许可证。

## 10. 原始项目

- HL Dataset: <https://github.com/michelecafagna26/HL-dataset>
- HSSBench: <https://github.com/Zhaolu-K/HSSBench>
- MM-MoralBench: <https://github.com/BeiiiY/MM-MoralBench>
- ValueGround: <https://github.com/NL2G/ValueGround>
- VULCA-Bench: <https://github.com/vulca-org/vulca-cultural-visual-benchmark>
