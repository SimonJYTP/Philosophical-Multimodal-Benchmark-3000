# PHILBENCH-3000 evaluation kit

本目录把模型测试所需的实验约定、Prompt 和结果字段固定下来。

- `PROTOCOL.zh-CN.md`：主评测、消融、统计与论文报告规范。
- `prompts.json`：机器可读的统一 Prompt；正式运行时记录 `prompt_id` 与文件 SHA-256。
- `schemas/prediction.schema.json`：逐题原始结果 JSONL 的记录规范。
- `schemas/run_manifest.schema.json`：每次模型运行的配置与可复现信息。
- `templates/model_registry.csv`：待测模型登记表。
- `templates/metrics_long.csv`：长表指标模板。
- `templates/human_scores.csv`：HL 自由文本盲评模板。
- `../scripts/compare_runs.py`：对 P0/P1 或 correct-image/control 运行做逐题配对比较。

正式测试前：

1. 固定 benchmark commit、`data/query.json` 哈希和本目录文件哈希。
2. 仅用 `dev` 做接口调试和 Prompt 修订。
3. 冻结 Prompt 后再运行 `test`；不得根据 test 结果继续改 Prompt。
4. 推理进程只能读取 `data/query.json` 和图片，不得读取 `answer_key.json`、`benchmark.jsonl` 或 `source_snapshots/`。
5. 每个输出同时保存原始响应和解析后的 `prediction`；`prediction` 可直接交给 `scripts/evaluate.py`。

## 最短可运行示例

先用 mock 后端确认环境，不会访问网络或消耗额度：

```powershell
py -3 .\scripts\run_models.py --provider mock --model mock-v1 --split dev --families visual_multiple_choice_qa --limit 2 --output-dir .\outputs\evaluation\smoke
py -3 .\scripts\analyze_results.py .\outputs\evaluation\smoke\predictions.jsonl --split dev --families visual_multiple_choice_qa --allow-partial --bootstrap-samples 100
py -3 .\scripts\compare_runs.py .\outputs\evaluation\smoke\predictions.jsonl .\outputs\evaluation\smoke\predictions.jsonl --split dev --families visual_multiple_choice_qa --allow-partial --bootstrap-samples 100 --output-dir .\outputs\evaluation\smoke-comparison
```

真实 API 的共同模式：

```powershell
$env:VLM_API_KEY='YOUR_KEY'
py -3 .\scripts\run_models.py --provider openai-compatible --base-url https://YOUR_PROVIDER_API/v1 --model EXACT_MODEL_ID --api-key-env VLM_API_KEY --split dev --families multimodal --prompt-suite P0 --limit 10 --output-dir .\outputs\evaluation\model-dev
```

OpenAI Responses、Anthropic、Gemini 以及正式 P0/P1、无图/错图对照的完整命令见仓库根目录 `README.md`。

## 默认行为

- 默认主语言为英语，默认 Prompt 为 P0。
- `multimodal` 只选择五个有本地图像的任务；dev 258 条，test 260 条。
- VULCA 是无图文本代理任务，并缺少可供模型解释标签 ID 的完整 codebook，因此不会被默认运行。
- 结果目录位于 `outputs/evaluation/`，已被 `.gitignore` 排除，避免误上传 API 响应或受限制内容。
- 运行器只读取 `data/query.json`；评分器才读取答案文件。
