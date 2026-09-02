# HSSBench 本地说明

- 全名：HSSBench: Benchmarking Humanities and Social Sciences Ability for Multimodal Large Language Models
- 用途：评估多模态大模型在人文与社会科学中的跨学科、多语言理解与推理能力。
- 任务设置：选择题/开放题；Direct/Chain-of-Thought 两类提示设置。
- 规模：13,152 条题目；9,725 个唯一图像路径。
- 语言：英语、中文、西班牙语、法语、阿拉伯语、俄语。
- 六大类别：Geography 3,562；History 2,496；Art 2,188；Culture 2,039；Social science 1,434；Economy 1,433。

## 已保存内容

- `repository/data/data-all.json`：完整 13,152 条多语言题目。
- `repository/data/data-open.jsonl`：开放题数据。
- `repository/data/pic_1.zip` 至 `pic_10.zip`：共 9,725 个文件，与 `data-all.json` 的唯一 `pic_path` 数一致。
- `repository/eval/json_answer_correction.py`：答案抽取与准确率统计脚本。
- `papers/HSSBench_arXiv_2506.03922.pdf`：arXiv v4（2026-08-11 修订）论文 PDF。

## 来源与版本

- GitHub：<https://github.com/Zhaolu-K/HSSBench>
- Hugging Face：<https://huggingface.co/datasets/dozo/HSSBench>
- arXiv：<https://arxiv.org/abs/2506.03922>
- ICLR 2026：<https://proceedings.iclr.cc/paper_files/paper/2026/hash/7972f3735e104a54715922aa416fde1b-Abstract-Conference.html>
- 本地仓库提交：`255842a7785cd749d99af1ef271fd032db70839c`

注意：官方 GitHub 仓库未提供独立 LICENSE 文件，使用和再分发前需进一步确认许可。

