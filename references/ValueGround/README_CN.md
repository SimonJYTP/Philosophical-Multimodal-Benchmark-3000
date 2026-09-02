# ValueGround 本地说明

- 全名：ValueGround: Evaluating Culture-Conditioned Visual Value Grounding in MLLMs
- 用途：测试模型能否把国家/文化条件下的价值倾向真正 grounding 到视觉选项，而不是只依赖文本价值知识。
- 核心设计：基于 World Values Survey，把相反的回答选项视觉化为最小对比图像对；输入国家、问题与图像对，模型选择更符合该国价值倾向的图像。
- 论文实验：6 个 MLLM、13 个国家；当前 arXiv v3 报告平均准确率从文本条件 72.8% 降到视觉条件 62.6%。

## 已保存内容

- `repository/README.md`：官方占位仓库。
- `papers/ValueGround_arXiv_2604.06484.pdf`：arXiv v3（2026-05-29 修订）论文 PDF。

## 公开状态

截至 2026-09-01，官方仓库仍只有 README，并明确写明 `Code and dataset will be released soon.`。因此当前可用于方法设计和 Related Work，但无法运行作者的正式数据与评测代码。

## 来源与版本

- GitHub：<https://github.com/NL2G/ValueGround>
- arXiv：<https://arxiv.org/abs/2604.06484>
- World Values Survey：<https://www.worldvaluessurvey.org/>
- 本地仓库提交：`e39ac9f646a9bfd79c122fb493fc21ddc94e5e7e`

注意：官方 GitHub 仓库未提供独立 LICENSE 文件。

