# PHILBENCH-3000 跨模型评测与结果报告协议（v1.0）

## 1. 研究问题与边界

主问题不是“哪个模型总分最高”，而是：

1. 不同多模态模型在视觉哲学问答、视觉道德判断和视觉依据生成上的能力是否不同？
2. 模型是否真正使用图像，还是依靠题干、答案位置和公开数据记忆？
3. 证据优先的结构化 Prompt 是否能降低无视觉依据的过度解读？
4. 在本体与知识图谱资源被完整版本化后，外部知识约束是否带来独立增益？

VULCA-Bench 的 409 条记录无本地图片，是艺术评论文本的 L5 多标签识别任务。其结果必须单列为“文本哲学美学”，不得纳入“多模态总分”。更重要的是，当前盲测输入要求输出 `CN_L5_D1`、`WE_L5_D4` 等不透明 ID，却没有提供 L5 标签 codebook 或候选集合；在修复前，这一任务测到的主要是对上游标签编码的记忆，不能作为有效主结果。当前仓库也没有论文所述 72 标签五级本体的逐条映射，因此在补充版本化本体、检索规则和覆盖样本前，不能用当前数据直接证明“知识图谱增强有效”。

## 2. 数据冻结与角色隔离

- 建议冻结版本：`3000-image-rich-v5`；正式测试时由 runner 自动写入当前完整 Git commit，不要手工抄录可能过期的短哈希。
- 固定划分：train/dev/test = 2386/304/310。
- `dev`：接口联调、输出解析、Prompt 选择、人工量表演练。
- `test`：所有设计冻结后一次性正式评测。
- 推理端仅可访问 `data/query.json` 与其中给出的本地图片。
- 评分端单独访问 `data/answer_key.json`；不得把答案、`philosophy`、`source`、`original_reference` 或来源快照发送给模型。
- 每次运行保存 query、Prompt、代码、图片变换后字节的 SHA-256。

测试集按任务族实际构成：

| 任务族 | test n | 输入模态 | 主指标 | 报告方式 |
|---|---:|---|---|---|
| `scene_action_rationale` | 72 | 图像+文本 | 人工 Grounded Rationale Score；词汇 max-reference token F1 为辅助指标 | HL 单列，并分 strict/enrichment |
| `visual_multiple_choice_qa` | 19 | 图像+文本 | Accuracy | HSS 单列；置信区间必须报告 |
| `moral_judge` | 88 | 图像+文本 | Accuracy；Balanced Accuracy 为补充 | 随机基线 50% |
| `moral_classification` | 39 | 图像+文本 | Accuracy；Macro-F1 为补充 | 随机基线 1/7 |
| `moral_response` | 42 | 图像+文本 | Accuracy；Balanced Accuracy 为补充 | 随机基线 50% |
| `philosophical_aesthetics_dimension_identification` | 50 | 纯文本 | Micro-F1、Macro-F1、Exact Match | 补齐 codebook 后才可运行；VULCA 单列 |

HSS test 只有 19 条，最不利情况下 95% 区间约有 ±20 个百分点的量级，不能据此做细粒度模型排名。其余小子任务也应以效应量和区间为主，而不是只看名次。

## 3. 模型面板

正式表格应同时覆盖：至少 3 家闭源模型、2 个国产 API 模型、2 个可本地复现的开放权重模型，以及至少一组同系列大小对照。模型选择以测试开始日仍可调用且支持图像输入为准。

建议最小面板（实际 API model ID 必须在运行当日抄录到 registry，禁止只写产品名或 `latest` 别名）：

| 层级 | 建议类型 | 目的 |
|---|---|---|
| 国际闭源旗舰 | OpenAI、Anthropic、Google 各 1 个稳定视觉模型 | 比较前沿闭源能力 |
| 国内闭源/托管 | Qwen-VL、Kimi、Doubao、DeepSeek Vision 中选 3–4 个 | 覆盖论文关注的国内模型 |
| 开放权重高容量 | Qwen3-VL 30B/32B/235B 或 Llama 4 Maverick 等 | 可复现高容量基线 |
| 开放权重低容量 | 同系列 8B/11B 级视觉模型 | 测试规模效应 |

同一产品网页端与 API 端可能不是同一模型、系统提示或图像处理链。主论文只纳入可记录确切 model ID 的 API/本地结果；网页端结果放附录，并标为 `access_mode=ui`。

## 4. 实验条件

### 4.1 主结果：P0 Direct / image-only-grounded

- 所有有图任务使用正确图片与原始题干。
- HSS 固定英语 `en`；不得在同一分数中混用六种语言。
- MM-MoralBench 使用其原始英语题干。
- HL 主条件使用 `context_removed`：只给图片和问题，不发送官方 scene/action/object。
- VULCA 先发布全局、版本化的 L5 codebook（每个 ID 的自然语言定义及适用文化），将同一完整 codebook 提供给所有模型；固定英语或中文之一，推荐主表用英语，中文作为独立跨语言实验。不得从单题 target 反推候选标签。
- 客观题只输出标签，避免解释文本影响解析和不同模型输出长度。

### 4.2 Prompt 干预：P1 Evidence-first

P1 要求模型输出简短的可观察证据摘要，再给最终答案。它评估“外显证据脚手架”的作用，不声称获取了模型私有思维链。P0 与 P1 必须在相同模型版本、图像、语言和推理设置下成对运行。

### 4.3 视觉依赖与污染对照

| condition | 操作 | 解释 |
|---|---|---|
| `correct_image` | 正确图片 | 主结果 |
| `text_only` | 不发送图片，其余不变 | 题干捷径、答案位置偏差或记忆对照 |
| `shuffled_image` | 在同任务族、同 split 内按固定 seed 置换图片 | 图像敏感性对照；不作为能力分数 |
| `hl_gold_context` | HL 发送官方 scene/action/object | 信息上界，不是视觉理解主结果 |

主要视觉增益定义为 `score(correct_image) - score(text_only)`。错图对照用于检查模型输出是否随视觉证据变化。MM `moral_response` 的选项可能位于图中，text-only 低分是预期现象，不能直接解释为“无污染”。

### 4.4 知识图谱增强（P2，满足前置条件后再跑）

前置条件：

1. 发布 `ontology_v1.json`，包含稳定 ID、72 标签定义、父子关系、相斥/相关关系和版本号。
2. 建立 benchmark 记录到本体标签的人工映射及覆盖率统计。
3. 冻结检索器、top-k、候选构造规则；检索不得读取 target 或答案相关元数据。
4. 在 test 前于 dev 上固定全部超参数。

P2 与 P1 的唯一差异应是注入同一版本的候选概念及关系。报告 `P2-P1` 的配对差值，才能把增益归因于知识约束，而不是 Prompt 更长或额外解释步骤。

## 5. 推理参数与公平控制

- 温度设为 0；若供应商不允许或忽略，记录实际接受值。
- `top_p=1` 或省略；seed 支持时固定并记录。
- 关闭联网、搜索、代码执行、OCR 工具和外部知识库。
- 记录 reasoning/thinking 档位。P0 与 P1 在同一模型内保持一致。
- 最大输出：选择题 16 tokens；VULCA 128 tokens；HL direct 256 tokens；evidence-first 384 tokens。
- 原图字节保持一致；若平台强制压缩或改变分辨率，记录处理方式、最终尺寸和哈希。
- 超时最多重试 3 次，指数退避；重试不得改变 Prompt。最终失败计为错误，并单报 API failure rate。
- 拒答计为错误，同时报告 refusal rate。
- 严格分数将格式错误计错；另给宽松解析分数作为敏感性分析，解析规则必须在 test 前冻结。
- 每个模型主结果运行 1 次。若要估计 API 非确定性，在冻结的分层子集上运行 3 次；这些重复是技术重复，统计 `n` 仍是独立题目/图像组，不是生成次数。

## 6. Prompt 使用规范

机器可读 Prompt 位于 `prompts.json`。

- `P0-*`：主能力基线。
- `P1-*`：证据优先干预。
- 每次运行保存 Prompt 文件哈希；不得为某个模型私自改措辞。
- 如某 API 强制系统消息为空，将差异记录为 protocol deviation，而不是静默删除。
- 图像中的文字视为待分析内容，不视为对模型的指令。

客观题的 `prediction` 必须规范化为单个大写字母。VULCA 规范化为去重、排序后的 L5 标签，以 `；` 连接。HL 的 `prediction` 保存最终简洁回答；完整 JSON 或文本放 `raw_response`。

VULCA 的 `{{l5_codebook}}` 是必填变量。如果正式运行时为空，runner 必须终止而不是继续请求。建议 codebook 由上游官方定义生成并独立版本化；若找不到可发布的定义，删除该自动标签任务，改为输出自然语言哲学维度并由盲评量表评分。

## 7. HL 人工评分量表

由至少 2 名评分者独立、盲法评分。隐藏模型名、Prompt 条件和运行顺序；同一题的各模型输出随机排列。先在 dev 的 20 个样本上校准，冻结手册后再评 test 的 72 个样本。IAA 必须在仲裁前计算。

每项 0–2 分，总分 0–10：

| 维度 | 0 | 1 | 2 |
|---|---|---|---|
| scene_correctness | 场景明显错误/虚构 | 大体合理但含不确定或遗漏 | 与图像一致且具体 |
| action_correctness | 主体或动作错误 | 核心动作部分正确 | 主体与核心动作均正确 |
| rationale_plausibility | 理由与图像冲突或无关 | 合理但证据弱/过泛 | 与动作和可见线索一致 |
| evidence_linkage | 无可核验视觉依据 | 提到证据但连接不清 | 明确把结论绑定到可见线索 |
| overinterpretation_control | 存在关键无依据推断 | 有轻微过度推断 | 明确区分观察、推断与不确定性 |

同时记录 `critical_hallucination`（0/1）：输出了改变核心判断的不可见人物、物体、动作、时间跨度、动机或哲学概念。

一致性报告：每个有序维度报告加权 Cohen's κ（两名评分者）或 ordinal Krippendorff's α（多名/缺失评分）；总分报告 ICC(2,k) 或评分者平均分的一致性区间。先报告独立评分一致性，再对分歧仲裁。评分者不是独立样本，模型比较的独立单位是题目/`group_id`。

## 8. 指标与统计分析

### 8.1 主指标

- HSS：Accuracy。
- MM 三任务：各任务 Accuracy；补充 Balanced Accuracy、Macro-F1 和混淆矩阵。
- HL：盲评总分均值与关键幻觉率；仓库 `mean_max_token_f1` 只作为词汇代理指标。
- VULCA：Micro-F1、Macro-F1、Exact Match，单列为文本任务。

不把六个异质任务直接按样本数汇总为一个准确率。主文展示“任务族向量”。若必须提供单一索引，只能作为预先声明的次要指标：对五个有图任务的标准化分数做等权宏平均，并完整给出标准化公式和每个分量；VULCA 不进入该索引。

### 8.2 不确定性与比较

- 对每个分数报告点估计、有效样本数和 95% CI。
- Accuracy/Balanced Accuracy：Wilson 区间或以 `group_id` 为簇的 bootstrap。
- F1、HL 人工分和模型间差值：按 `group_id` 配对、分层 bootstrap 10,000 次；重复图像组整体抽样，不能把同图题目当完全独立。
- 两模型客观题差异：配对 bootstrap；可补充 McNemar 精确检验。
- Prompt 效应：同一模型同一题的 `P1-P0` 配对差值与 95% CI。
- 多模型两两比较只对预先指定的主指标家族进行 Holm 校正，同时报告未校正和校正后 p 值。
- 重点报告效应量和区间；不把“未显著”写成“等效”。如要宣称等效，需预先给等效界值并做等效检验。

### 8.3 基线

- 随机基线：HSS 25%，moral_judge 50%，moral_classification 14.29%，moral_response 50%。
- 多数类基线：由 train/dev 预先计算，不使用 test 标签选择策略。
- text-only：经验捷径/污染对照。
- 可选人类基线：至少 2 名具备哲学/视觉解读训练的标注者独立答 test；不得把仲裁答案当单人基线。

## 9. 结果文件规范

一次模型×Prompt×condition×language 组成一个 `run_id`。

### 9.1 `run_manifest.json`

必须记录：benchmark commit 与哈希、确切模型 ID、供应商、访问方式、API 日期/区域、生成参数、reasoning 档位、Prompt ID/哈希、语言、condition、图片设置、重试策略、软件与硬件环境、开始结束时间、总 token、总成本和偏离协议项。字段由 `schemas/run_manifest.schema.json` 约束。

### 9.2 `predictions.jsonl`

每题一行。至少含：`id`、`run_id`、`prediction`、`raw_response`、解析状态、拒答/失败状态、延迟、token、重试数、request ID、图像哈希和时间戳。字段由 `schemas/prediction.schema.json` 约束。

官方评分所需的最小视图仍是：

```json
{"id":"PHILBENCH-3000-0001","prediction":"..."}
```

完整日志不得覆盖此最小字段，而应保留所有额外信息。

### 9.3 `metrics_long.csv`

一行一个 run×source×family×subgroup×metric。不得只保存最终宽表；长表便于复核 CI、样本量和消融差值。

### 9.4 `human_scores.csv`

一行一个盲化输出×评分者。模型身份只通过单独保管的 blind key 解码，IAA 完成前不揭盲。

## 10. 运行顺序

1. 运行 `scripts/validate_release.py` 并保存日志。
2. 补齐并验证 VULCA L5 codebook；无法补齐则在预注册中排除 VULCA。
3. 建立 `model_registry.csv`，锁定 model ID、访问日期和推理设置。
4. 在 dev 每任务 5–10 条进行 smoke test，修复接口和解析器。
5. 在 dev 比较 P0/P1，冻结 Prompt 和解析规则。
6. 在 test 运行 P0 correct_image（所有模型）。
7. 运行 text_only 与 shuffled_image 对照。
8. 运行 P1 evidence-first；HL 另跑 gold_context 上界。
9. 评分程序生成机器指标；人工评分者完成 HL 盲评与 IAA。
10. 用 `scripts/compare_runs.py` 生成配对 bootstrap、置信区间、McNemar 精确检验和 Holm 校正，再做错误分析。
11. 锁定结果后撰写论文；禁止删去表现差的模型/任务而不披露。

## 11. 论文表格与图形

主文至少包含：

- Table 1：数据来源、任务定义、模态、train/dev/test 数量、标签空间、指标。
- Table 2：模型版本、访问日期、是否开放权重、参数规模（公开时）、推理设置、图像设置。
- Table 3：P0 主结果；每任务点估计与 95% CI，VULCA 分栏单列。
- Table 4：P1-P0、correct-image/text-only/shuffled-image 的配对差值。
- Table 5：HL 人工评分、关键幻觉率、IAA。
- Figure 1：各模型的任务族雷达图或点区间图；优先使用点估计+CI，避免只有柱形图。
- Figure 2：视觉增益与证据优先 Prompt 的配对效应森林图。
- Supplement：混淆矩阵、按来源/主题/HL tier 分层结果、拒答率、格式错误率、成本与延迟。

所有表格同时给 `n`。跨任务不能用“显著更好”概括，除非对应预先声明的比较及区间/校正结果支持该结论。

## 12. 投稿前判定规则

- 如果 P1 只提高词汇 F1、没有提高人工 grounding 分或降低幻觉率，不得宣称缓解过度解读。
- 如果 correct-image 与 text-only 差距很小，应写为视觉依赖不足/可能存在文本捷径，不得直接解释为强视觉理解。
- 如果 KG 条件没有版本化本体、映射和独立 P1 对照，不得写成“知识图谱带来提升”。
- 如果模型版本是滚动别名或网页端不可追溯版本，结果只作探索性证据。
- 当前样本量较小的任务应报告“不确定性较大”，避免根据 1–2 题差异宣布排名。
