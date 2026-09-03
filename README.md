# Philosophical Multimodal Benchmark 2800 — Image-Rich (v4)

这是面向“哲学意味多模态理解”研究的图像增强版数据集，共 **2,800 条**，其中 **1,912 条具有可直接读取的本地图片，覆盖率 68.29%**，达到不少于 65% 的目标。

本版不是简单地为文本记录配任意图片，而是使用各 benchmark 的原始图片映射：HL 与 HSS 使用原数据图片，MM-MoralBench 使用作者公开的 `M3oral_images.zip`，VULCA 因第三方艺术图像权利限制仍只保留来源引用。

v4 修复了三项会影响有效性的发布问题：盲测输入不再携带答案相关元数据；VULCA 目标严格限定为提示所要求的 L5 标签；MM-MoralBench 不再保留“本地无图像”的过期上下文。该版本另提供独立发布验证器和可复现的分类/多标签评分脚本。

## 1. 数据构成

| 来源 | 条数 | 本地图片 | 图片覆盖率 | 主要用途 |
|---|---:|---:|---:|---|
| HL Dataset | 650 | 650 | 100% | 场景、行动和理由中的责任、认知、审美、宗教及生命处境理解 |
| HSSBench | 182 | 182 | 100% | 官方 Philosophy/Ethics 视觉选择题与多语言推理 |
| MM-MoralBench | 1,080 | 1,080 | 100% | 六类道德基础上的判断、分类和回应 |
| VULCA-Bench | 888 | 0 | 0% | 多文化艺术评论中的 L5 哲学美学维度识别（本版为文本代理任务） |
| ValueGround | 0 | 0 | — | 论文和方法参考；官方数据尚未公开 |
| **合计** | **2,800** | **1,912** | **68.29%** |  |

数据划分：`train` 2,235 条、`dev` 278 条、`test` 287 条。划分采用固定哈希并按来源、任务和主题分层；完全相同的图片内容被强制分配到同一划分，可由构建脚本复现。

## 2. 图像增强策略

### HL Dataset：650 条

HL 分为两个可审计层级：

- **严格层 237 条**：同一哲学主题在场景/行动/理由标注中至少命中 2 次，官方平均置信度 ≥ 3.5。
- **图像增强层 413 条**：只接受行动或理由标注中的 1 条直接主题证据，官方平均置信度 ≥ 4.5；仅场景词命中的候选全部排除。

新增层不是与严格层等价的“金标准”。`audit.hl_selection_tier`、证据文本、证据轴和质量分均已保留，论文可进行严格层/增强层消融实验。

HL 六个主题配额：认识论 270、伦理学 143、美学 135、政治哲学 63、宗教哲学 25、生命哲学 14。

### HSSBench：182 条

- 仅保留官方 `Philosophy` 或 `Ethics` 标签记录。
- 前一版发现的一组三条同题、答案 B/C/B 的冲突题已经去重，保留原核心且与多数答案一致的 B 项。
- 规范化后的 182 个题干全部唯一。

### MM-MoralBench：1,080 条

- 六种道德基础各 180 条：Care、Fairness、Loyalty、Authority、Sanctity、Liberty。
- 每种基础包含判断 90、分类 45、回应 45，避免类别或任务失衡。
- 1,080 张图片均从作者公开的 `M3oral_images.zip` 按原始 `judge_*`、`classification_*`、`response_*` 引用映射并提取。
- 每个选中记录都通过压缩包成员存在性、解压 CRC 和图片文件头检查。
- 检出 63 组被不同 MM 任务复用的完全相同图片，共涉及 126 条记录；这些记录保留为不同任务，但根据图片 SHA-256 绑定到同一 train/dev/test 划分，避免视觉内容泄漏。

### VULCA-Bench：888 条

- 只保留官方 L5 Philosophical Aesthetics 维度且质量分 ≥ 85 的记录。
- 按八种文化传统和哲学主题分层取样。
- 为遵守官方权利边界，不重新分发第三方艺术图片；`original_reference` 和权利清单仍完整保留。

## 3. 目录结构

```text
Philosophical_Multimodal_Benchmark_2800_ImageRich/
├─ README.md
├─ dataset_card.json
├─ schema.json
├─ data/
│  ├─ benchmark.jsonl                # 完整数据，含答案
│  ├─ query.json                     # 无 target 的盲测输入
│  └─ answer_key.json                # 独立答案文件
├─ splits/
│  ├─ train.jsonl
│  ├─ dev.jsonl
│  └─ test.jsonl
├─ images/
│  ├─ HL_Dataset/                    # 650 张
│  ├─ HSSBench/                      # 182 张
│  └─ MM-MoralBench/                 # 1,080 张
├─ source_snapshots/
│  └─ selected_source_records.jsonl  # 2,800 条原始来源快照
├─ review/
│  ├─ philosophical_multimodal_benchmark_2800_image_rich.csv
│  └─ philosophical_multimodal_benchmark_2800_image_rich_review.xlsx
├─ references/                       # 论文、官方说明、BibTeX 和权利材料
└─ scripts/
   ├─ build_dataset.py
   ├─ validate_release.py
   └─ evaluate.py
```

## 4. 记录格式

`data/benchmark.jsonl` 每行是一条完整 JSON 记录：

```json
{
  "id": "PHILBENCH-2800-0001",
  "split": "train",
  "task": {
    "family": "scene_action_rationale",
    "output_type": "free_text_rationale"
  },
  "input": {
    "prompt": {"zh": "...", "en": "..."},
    "context": {"zh": null, "en": {}},
    "options": null,
    "image": {
      "path": "images/HL_Dataset/PHILBENCH-2800-0001.png",
      "original_reference": "...",
      "availability": "..."
    }
  },
  "target": {"answer": "...", "type": "free_text_rationale"},
  "philosophy": {
    "primary_theme": "...",
    "secondary_themes": [],
    "validation": {
      "status": "passed",
      "authority": "image_enrichment_action_rationale_evidence",
      "criterion": "...",
      "evidence_count": 1,
      "evidence": [{"axis": "rationale", "text": "..."}],
      "quality_score": 4.6667
    }
  },
  "source": {
    "benchmark": "HL Dataset",
    "original_id": "...",
    "original_split": "...",
    "url": "...",
    "category": "...",
    "license_or_rights_note": "..."
  },
  "audit": {
    "hl_selection_tier": "image_enrichment",
    "group_id": "...",
    "content_hash": "...",
    "philosophy_pass": true,
    "selection_version": "2800-image-rich-v4"
  }
}
```

## 5. 快速使用

### 5.1 读取数据与图片

```python
import json
from pathlib import Path

root = Path(".")
with (root / "data" / "benchmark.jsonl").open(encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

image_records = [r for r in records if r["input"]["image"]["path"]]
assert len(records) == 2800
assert len(image_records) == 1912

sample = image_records[0]
image_path = root / sample["input"]["image"]["path"]
assert image_path.exists()
```

### 5.2 盲测流程

1. 只向被测模型提供 `data/query.json`。
2. 保存 `{"id": "...", "prediction": "..."}` 格式的预测。
3. 推理结束后使用 `data/answer_key.json` 按 ID 对齐评分。

`query.json` 顶层严格只保留 `id`、`split`、`task`、`input`；`philosophy`、`source`、`audit` 和本地图像的原始文件名均已移除。不要在推理阶段加载 `benchmark.jsonl` 或 `answer_key.json`，避免答案泄漏。

### 5.3 按严格程度使用 HL

```python
hl_strict = [
    r for r in records
    if r["source"]["benchmark"] == "HL Dataset"
    and r["audit"].get("hl_selection_tier") == "strict"
]

hl_enrichment = [
    r for r in records
    if r["source"]["benchmark"] == "HL Dataset"
    and r["audit"].get("hl_selection_tier") == "image_enrichment"
]

assert len(hl_strict) == 237
assert len(hl_enrichment) == 413
```

论文主结果可以使用全部 650 条，同时单独报告严格层成绩；如果研究只接受更保守的哲学证据，可仅使用 237 条严格层。

## 6. 推荐评测指标

| 任务族 | 输入 | 输出 | 主指标 |
|---|---|---|---|
| `scene_action_rationale` | 图像 + Scene/Action/Object 上下文 | 自由文本 Rationale | 人工量表 + 预先声明的语义指标 |
| `visual_multiple_choice_qa` | 图像 + 多语言题干与选项 | A–D | Accuracy |
| `moral_judge` | 图像 + 道德判断题干 | A/B | Accuracy |
| `moral_classification` | 图像 + 六类道德基础选项 | A–G | Accuracy |
| `moral_response` | 含文字的图像 + 回应选择题干 | A/B | Accuracy |
| `philosophical_aesthetics_dimension_identification` | 艺术评论文本（本版无本地图像） | L5 标签集合 | Micro-F1、Macro-F1、Exact Match |

- HSSBench 与 MM-MoralBench：Accuracy，并分别按任务与道德基础报告。
- VULCA-Bench：标签集合的 Micro-F1、Macro-F1 和 Exact Match。
- HL Dataset：人工量表（相关性、因果合理性、哲学关联、幻觉）结合语义相似度；不建议只使用字面 Exact Match。
- 跨来源：先报告各来源指标，再进行明确归一化后的等权宏平均，不要把异质任务直接混成一个 Accuracy。

对选择题与 VULCA L5 多标签任务，可直接运行：

```powershell
py -3 .\scripts\evaluate.py .\predictions.jsonl --split test
```

脚本报告各选择题任务的 Accuracy，以及 VULCA 的 Micro-F1、Macro-F1 和 Exact Match；HL 自由文本任务会明确列为需另行进行语义/人工评分，不会用不恰当的字面匹配混入总分。预测文件必须与所选划分的 ID 完全一致。

## 7. 重新构建

构建脚本只依赖 Python 标准库。默认从用户下载目录读取：

```text
Downloads/M3oral_images.zip
```

如果压缩包位于其他位置，先设置环境变量：

```powershell
$env:MM_MORAL_IMAGE_ARCHIVE='D:\path\to\M3oral_images.zip'
py -3 .\scripts\build_dataset.py
```

脚本会刷新数据、图片、来源快照、CSV 和参考材料，并执行全部质量断言。现有 Excel 审阅表作为静态快照会被保留；修改筛选逻辑后应从新 CSV 重新生成。

克隆发布仓库后无需原始源目录即可执行完整性验证：

```powershell
py -3 .\scripts\validate_release.py
```

## 8. 图片与许可边界

- HL Dataset：标注采用 Apache-2.0；图像和对象描述仍受 COCO 原始条款约束。
- HSSBench：官方仓库没有独立 LICENSE。182 张图片虽然来自官方压缩包，但公开再分发前仍应向作者或权利方确认。
- MM-MoralBench：图片来自作者 README 提供的公开图像包，但官方 GitHub 同样没有独立 LICENSE。内部研究使用和公开再分发是不同问题，公开发布前需确认许可。
- VULCA-Bench：benchmark 元数据、评论和工具使用 CC BY 4.0；该许可不自动覆盖第三方艺术作品图片。
- ValueGround：当前仅保存论文和仓库说明，没有虚构未发布数据。

相关论文、官方 README、许可证、VULCA 图像权利说明和逐条权利清单位于 `references/`。

## 9. 质量保证

`dataset_card.json` 保存当前所有自动检查结果，覆盖：

- 总量、来源配额、ID 与内容哈希唯一性；
- HL 严格层和图像增强层各自的证据/置信度要求；
- HSS 题干去重；
- MM 道德基础和任务配额；
- VULCA L5、质量阈值和文化配额；
- 1,912 个本地路径存在、图片来源分布正确、图片文件头有效；
- 1,912 个图像文件对应 1,849 个唯一图像内容，63 组复用图片均未跨越数据划分；
- 图片覆盖率 ≥65%；
- 划分组隔离、查询与完整记录严格对应、答案逐条精确对齐；
- 盲测查询不含答案相关元数据或本地原始文件名；
- VULCA 目标仅含 L5 标签且输入不包含目标标签；
- MM-MoralBench 上下文与本地图像可用状态一致；
- 无 Unicode 替换字符。

自动规则不能替代哲学专家复核。尤其是 HL 图像增强层，建议在论文定稿前进行分层随机抽样人工复核，并在方法部分明确其筛选规则。

VULCA 的 888 条记录由于第三方艺术图像权利边界，在此发布中只能按艺术评论执行文本代理评测，不能计入“具有本地视觉输入”的样本量。HSSBench 与 MM-MoralBench 的上游仓库没有独立 LICENSE；公开再分发前仍应取得权利方确认。仓库因此不附加一个覆盖全部内容的统一数据许可证。

就工程发布而言，v4 已可重复验证和评分；就论文发表而言，仍需补充新的专家复核/标注一致性统计、明确 HL 自由文本量表与评审流程，并实际运行基线模型形成定量结果表。仓库不会把尚未完成的实验伪装成基线结果。

## 10. 原始项目

- HL Dataset: <https://github.com/michelecafagna26/HL-dataset>
- HSSBench: <https://github.com/Zhaolu-K/HSSBench>
- MM-MoralBench: <https://github.com/BeiiiY/MM-MoralBench>
- ValueGround: <https://github.com/NL2G/ValueGround>
- VULCA-Bench: <https://github.com/vulca-org/vulca-cultural-visual-benchmark>
