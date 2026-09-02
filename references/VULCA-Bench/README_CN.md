# VULCA-Bench 本地说明

- 全名：VULCA-Bench: A Multicultural Vision-Language Benchmark for Evaluating Cultural Understanding
- 用途：评估 VLM 对多文化艺术图像的分层理解与双语艺术评论能力。
- 五层框架：L1 Visual Perception → L2 Technical Analysis → L3 Cultural Symbolism → L4 Historical Context → L5 Philosophical Aesthetics。
- 指标/工具：Dimension Coverage Rate（DCR）与 L1–L5 layer scoring。

## 已保存内容（canonical v2.1）

- `repository/data/vulca_bench.jsonl`：7,236 条 canonical 双语 critique/元数据记录。
- `repository/data/culture_subsets/*.jsonl`：8 个文化传统的精确子集。
- `repository/data/license_rights_manifest_v2_1.csv`：7,236 行图像权利与标注许可边界。
- `repository/evaluation/`：模型调用、DCR 与层级评分工具。
- `repository/release/v2.1/manifest.json`：发布计数、来源与 SHA-256。
- `papers/VULCA-Bench_arXiv_2601.07986.pdf`：arXiv v3 论文 PDF。

官方校验脚本已在本地通过：7,236 records、7,236 unique pair_id、7,236 unique ulid、236 unique covered dimensions、0 redistributed artwork image files。

## 版本边界

- 论文/历史快照：7,410 image–critique pairs、225 个文化特定维度。
- 当前 canonical v2.1：7,236 条记录、236 个唯一 covered dimensions。
- 写作和实验时不可混用这两组统计，应注明 paper-era 或 v2.1。

## 图像与许可

当前 canonical 仓库明确不重新分发第三方艺术图片。`image_path` 只是来源侧相对引用，不代表所有权、可下载 URL 或再分发许可。使用图像前必须阅读：

- `repository/IMAGE_RIGHTS.md`
- `repository/data/license_rights_manifest_v2_1.csv`

CC BY 4.0 适用于仓库分发的 benchmark 元数据、评论和工具，不自动覆盖艺术作品图像。

## 来源与版本

- Canonical GitHub：<https://github.com/vulca-org/vulca-cultural-visual-benchmark>
- 历史论文仓库：<https://github.com/yha9806/VULCA-Bench>
- arXiv：<https://arxiv.org/abs/2601.07986>
- 本地仓库提交：`57ffa5914b72de40eec98ba833796940a5644885`

