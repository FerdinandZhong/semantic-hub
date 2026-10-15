# 制药演示：两条文档到语义模型的故事线

更新：2026 年 10 月 14 日。[English version](pharma-intelligence-demo-story.md)。

**故事一为已有模型补充证据。故事二把图表中的已审核数据转成独立模型。**
所有正式审核和发布操作均由演示者完成。

| 故事 | PDF 物理页码 | 结果 | Playground 查询对象 |
| --- | --- | --- | --- |
| 一：澄清已有指标的范围 | 14 | 为制药情报模型附加证据 | 已发布指标及第 14 页的文档引用答案 |
| 二：把图表转成可查询事实 | 4、5 | 创建独立数据源及语义模型 | 人工核对并批准的数据行 |

```text
故事一：PDF 第14页 → 审核证据关联 → 已有草稿 → 验证 → 发布 → 查询
故事二：PDF 第4、5页 → 审核数值行 → 新草稿 → 验证 → 发布 → 查询
```

## 演示前准备

1. 打开 [Semantic Hub](http://localhost:8084/demo)。
2. 确认目录中存在 **Pharmaceutical Industry Intelligence & New Drug Analysis**。
3. 不要选择 **Pharma sample**；后者演示合成的批次质量数据。
4. 在 **Model configuration** 中测试语义生成和 Playground 的 `gpt-4o` 配置。
5. 准备 [EFPIA 2026 原始 PDF](https://www.efpia.eu/media/owqczcqz/the-pharmaceutical-industry-in-figures-2026.pdf)。
6. 打开下文链接的 SQL 文件及数据行填写表。

本机文件：`/tmp/helios-real-documents-20261013/efpia-industry-figures-2026.pdf`。
所有页码均为从 1 开始的 PDF 物理页码。

10 月 14 日的清理已归档旧的 **EFPIA New Medicine Sales by Region** 模型及对应上传记录。
原有四个数据集、制造业 `v1.0`、制药情报工作区均保持不变。
备份目录：`/tmp/helios-efpia-reset-20261014-090454/`。
本次准备没有在正式演示工作区创建或发布新模型。

## 故事一：解释为什么 74.1% 和 54.7% 回答不同问题

建议预留 12–15 分钟，另加 AI 处理时间。

### 第一幕：打开已有模型

1. 选择 **Pharmaceutical Industry Intelligence & New Drug Analysis → Open Studio**。
2. 查看 `industry_observations` 表和 `us_new_medicine_sales_share_percent` 指标。
3. 展示 **74.1%**，说明它属于 2020–2024 年上市新药的美国销售占比。
4. 点击 **Add supporting material**，进入保留当前模型选择的文档库。

讲解：

> 模型已经有一个销售占比指标。
> 新报告中还有一个看起来相似的百分比。
> 我们通过证据审核和明确的定义，保留两者的区别。

### 第二幕：上传 PDF，提取第 14 页

1. 选择 **New document**，上传原始 PDF。
2. 找到 **1. Analyze pages with AI**。
3. 输入 `14`，点击 **Analyze selected pages with AI**。
4. 展开 **Review page results**，对照原页、提取文字及候选数据行。
5. 检查世界药品市场图及其来源说明。
6. 本故事不要使用 **Approve reviewed rows as a new draft model**。

第 14 页的 **54.7%** 属于**北美，即美国和加拿大**。
其范围是 **2025 年全球零售及医院处方药市场**，按**出厂价格**计量。
该页的欧洲范围包含白俄罗斯、土耳其、俄罗斯和乌克兰。
这与第 4 页的新药上市范围和地区定义不同。
下半页是 2024 年药品零售价格构成，不纳入本次关联。

讲解：

> 第 14 页提供整个处方药市场的背景。
> 北美不等于美国，整个处方药市场也不等于新上市药品。
> 我们把它作为范围排除依据，不用 54.7% 替换 74.1%。

### 第三幕：关联已有模型

1. 展开独立卡片 **Add evidence to an existing semantic model**。
2. 保留 **Evidence to match → Analyzed pages: 14**。上方的全文摘要是可选步骤。
3. 保持 **Use embedding similarity** 未勾选。
4. 点击 **Find model links**。
5. 展开 **Candidate model links**。
6. 在 **Filter by model** 中选择制药情报模型。
7. 选择 **Suggested**，保留 **Highest relevance** 排序。
8. 在 **Search candidate links** 中依次搜索 `industry_observations.indicator page 14` 和 `us_new_medicine_sales_share_percent page 14`。切换搜索会保留已选项。
9. 找到 **Section: page 14**，核对原文与目标。
10. 只选择下表中含相关原文的关联。

| 目标 | 核对内容 | 关联用途 |
| --- | --- | --- |
| `industry_observations.indicator` | 整体处方药市场范围、北美地区定义 | 解释不同指标的范围 |
| `us_new_medicine_sales_share_percent` | 北美 54.7% 及对应市场说明 | 作为排除依据；不证明该指标的 74.1% 数值 |

已检查的原始 PDF 关键词匹配会返回这两个目标。
匹配默认限定第 14 页，包括该页原文和 AI 转录。
如需全文匹配，选择 **All extracted document text**。仍须核对页码和原文。
为了重复演示，优先使用原文 `page 14` 的候选，避免重复选择 AI 转录候选。
如果候选不同，不要批准无关目标。检查模型过滤条件，并使用原文关键词匹配路径。
当前界面没有任意指定目标的手动关联编辑器。

**Summarize document text** 可生成摘要和带引用的声明，但关键词匹配不依赖它。
Embedding 是可选排序方式，启用后候选顺序可能变化。
相关性分数不代表证据已经成立。

核对后填写自己的姓名，并使用以下审核备注：

```text
我已对照 EFPIA 2026 原始 PDF 核对物理页码 14。该页描述 2025 年按出厂价格计算的整体处方药市场，北美包含美国和加拿大。本次批准仅用于范围说明和排除依据，不证明也不替换第 4 页的美国新药销售占比 74.1%。本次不包含零售价格构成图。
```

11. 点击 **Approve selected links**。
12. 保持这些已批准关联处于选中状态。
13. 在 **Target model** 中选择制药情报模型。
14. 点击 **Apply approved evidence to draft**。
15. 点击 **Open Studio to draft with AI** 返回 Studio。

此操作附加文档证据和来源关系，不导入第 14 页的数值，也不修改 SQL。
画布中的证据边表示文档支持关系，不表示数据库连接。

### 第四幕：明确指标含义

建议直接编辑已有指标，避免演示时重新生成全部定义。
保留指标名称、表达式、单位和过滤条件。
在说明或排除规则中补充：

```text
Exclude total prescription-market shares. EFPIA page 14 reports North America (USA and Canada), not USA alone. Its 54.7% figure has a different population from this metric's 2020–2024 new-medicine launch cohort, measured using 2025 sales.
```

保存草稿。先完成证据附加，再修改定义；定义变化可能使旧候选关联过期。
如需展示 AI 生成，请逐项检查并明确应用候选修改。
不要宣称上传或附加文档会自动改变指标计算。

### 第五幕：验证并发布

打开[故事一参考 SQL](demo-inputs/story-1-pharma-reference.sql)。
为每个指标的验证字段复制对应的一条 SQL，不要一次粘贴整个文件。
本故事需要验证全部六个指标。

| 指标 | 预期结果 |
| --- | ---: |
| `novel_approval_count` | 46 |
| `evidence_patient_count` | 105 |
| `no_prior_adc_orr_percent` | 75 |
| `prior_adc_orr_percent` | 44 |
| `no_prior_adc_durable_response_percent` | 58 |
| `us_new_medicine_sales_share_percent` | 74.1 |

1. 保存草稿并运行验证。
2. 检查 SQL 对账、关系检查和文档证据。
3. 审核对象；仅在检查后使用批量批准。
4. 打开 **Versions & releases**。
5. 输入未使用的版本号，例如 `v1.0`，以及姓名和审核备注。
6. 勾选确认项，创建审核版本。
7. 发布该版本。
8. 如需激活普通样例查询，再选择 **Use for queries**。

审核备注示例：

```text
已审核六个初始指标及参考 SQL。附加 EFPIA 第 14 页作为范围说明和排除证据。保留美国新药销售占比的原有计算、2020–2024 年上市范围及 2025 年最新销售口径。
```

### 第六幕：查询已发布版本

1. 打开 **Playground**，选择已发布版本。
2. 输入 `What is the US share of sales for new medicines launched during 2020–2024?`。
3. 点击 **Interpret question**，核对指标和范围。
4. 点击 **Run this interpretation**，预期结果为 **74.1%**。
5. 输入 `How many FDA CDER novel drugs were approved in 2025?`，预期为 **46**。

使用 **Saved metrics** 可获得不依赖 LLM 解释的重复演示路径。
英文指标示例便于与指标定义匹配。文档问题也可以使用中文。

接着演示文档证据问答：北美在 2025 年整个处方药市场中占多少？
现有结构化模型没有这个指标，不能把 74.1% 当作答案。
1. 保持 **AI · query data + documents**，或选择 **Document evidence**。
2. 输入上述问题，点击 **Interpret question**。
3. 检查检索出的第 14 页原文。
4. 点击 **Answer from these documents**，预期得到来源报告的 **54.7%**。
5. 展开引用，检查页码、原文摘录及文档修订号。

所选发布版本必须包含已审核并应用到草稿的第 14 页附件。仅上传或应用到草稿还不够。
这条文档问答路径不需要新增参考 SQL。已有指标的发布验证要求仍然保留。
它直接引用文档陈述，不创建新的结构化指标。
若需要可复用的 54.7% SQL 指标，仍需创建审核后的结构化事实并验证指标。

讲解：“Hub 保留两种不同含义。SQL 从新药数据中计算 74.1%。已发布文档记录北美整体处方药市场的 54.7%。”

### 联合使用 SQL 和文档的 AI 问题

输入：`What is the US share of sales for new medicines launched during 2020–2024, and how does it differ from North America's share of the total prescription market in 2025?`
检查 SQL 与文档计划，点击 **Run AI query and answer**。
答案分别引用 SQL 的 74.1% 和第 14 页的 54.7%，并说明两者口径不同。
若问题是“北美在2020到2024年整个处方药市场中占多少”，应要求澄清。
2025 年的观察值不能回答该问题。

## 故事二：从第 4、5 页创建新模型

建议预留 15–20 分钟，另加 AI 处理时间。

### 第一幕：开启独立文档流程

1. 返回 **Supporting materials**。
2. 选择故事一的 PDF，并切换到最新文档修订。
3. 再次分析会创建新修订，保留故事一的审核结果和证据。
4. 在 **Pages to analyze** 输入 `4, 5`。
5. 点击 **Analyze selected pages with AI**。
6. 对照两页原图核查候选数据。

第二个故事使用 **Create a new semantic model**。
已有模型关联功能仍可使用，但不是必需步骤。
若需要独立的文档条目，也可以选择 **New document** 再次上传。

### 第二幕：核对九条数据

打开[数据行填写表 CSV](demo-inputs/efpia-pages-4-5-row-guide.csv)。
它是人工核对后的演示填写参考，不是实际 AI 提取结果。

| 页码 | Entity | Metric | Value | Unit | Period |
| --- | --- | --- | ---: | --- | --- |
| 4 | USA | New medicine sales share | 74.1 | % | Launches 2020–2024; sales 2025 |
| 4 | Europe Top 5 | New medicine sales share | 15.6 | % | Launches 2020–2024; sales 2025 |
| 4 | Japan | New medicine sales share | 3.6 | % | Launches 2020–2024; sales 2025 |
| 4 | Pharmerging | New medicine sales share | 2.9 | % | Launches 2020–2024; sales 2025 |
| 4 | Rest of the World | New medicine sales share | 3.8 | % | Launches 2020–2024; sales 2025 |
| 5 | Europe | Pharmaceutical R&D expenditure | 56344 | EUR million | 2024 |
| 5 | USA | Pharmaceutical R&D expenditure | 75895 | USD million | 2024 |
| 5 | Japan | Pharmaceutical R&D expenditure | 16607 | JPY million x 100 | 2024 |
| 5 | China | Pharmaceutical R&D expenditure | 114557 | CNY million | 2024 |

1. 只选择这九条已核查的数据。
2. 按 CSV 统一实体、指标、单位、时期和人群字段。
3. 保留 `2020–2024` 中的连接符，确保与 SQL 字符串一致。
4. Denominator 留空；不要编造未印出的分母。
5. Source quote 保留实际图表文字，并确认物理页码正确。
6. 排除第 4 页正文中的其他数值。
7. 排除第 5 页其他年份和下半页的平行进口图。

日本单位是 **百万日元 × 100**，不是普通的百万日元。
保留 16607 及该单位，不要擅自换算。
第 5 页的 Europe 研发系列不等于第 4 页的 Europe Top 5 销售范围。
不要把不同币种的研发数值直接相加或比较大小。

AI 提取结果可能变化。若缺少目标行，请在批准前重新分析并检查新候选。
当前表单不能任意添加缺失行。不要批准无关行来凑够九条。
后面的 SQL 专门对应这九条核对后的数据。

### 第三幕：创建草稿

1. 展开 **Approve reviewed rows as a new draft model**。
2. 输入标题 `EFPIA New Medicine Sales and R&D Evidence`。
3. 输入自己的审核姓名。
4. 核对两页后填写以下备注：

```text
我已对照 EFPIA 2026 PDF 的物理页码 4、5 核对九条图表数据。第 4 页包含五个地区的新药销售占比，范围为 2020–2024 年上市药品、2025 年最新销售。第 5 页包含四个地区的 2024 年研发投入。保留各自币种及单位，包括日本的百万日元乘以 100。排除其他年份、正文数值和平行进口图。数值分母保持未知，不跨指标或币种汇总。
```

5. 勾选确认项，点击 **Approve rows and create model**。
6. 点击 **Open created model in Studio**。
7. 检查两张表和画布中的来源关系。

预期结果：九条 `document_observations`、一条 `document_sources`、十个初始指标。
十个指标包含一个记录数指标和九个单值指标。
新模型已经包含原始文档及来源记录，无须再关联模型。
创建草稿不会自动发布。

### 第四幕：填写参考 SQL

初始指标名称类似 `observation_17_value`，具体编号取决于提取顺序。
不能假设 `observation_1` 就是美国。

1. 通过实体、指标含义和时期确认每个单值指标对应的数据行。
2. 将名称改为 CSV 中对应的 `metric_name`。
3. 保留初始表达式；它通过原始 observation ID 选择数据行。
4. 记录数指标保持 `reviewed_observation_count`。
5. 为每个指标复制[故事二参考 SQL](demo-inputs/story-2-efpia-reference.sql)中的对应语句。
6. 保存，并验证全部十个指标。

参考 SQL 通过业务标签、页码、单位和时期查找数据。
初始表达式通过 observation ID 查找数据。
比较两种查询路径，可以发现指标与数据行对应错误。
空结果或重复数据行会导致对账失败，需要检查标签或重复提取。
不要用 `SELECT 74.1` 之类的固定答案替代参考查询。
如果保留初始指标名，必须将参考 SQL 的 `AS` 别名改成完全一致的名称。

美国研发投入示例：

```sql
SELECT value AS us_rd_2024_usd_million
FROM document_observations
WHERE source_page = 5
  AND entity = 'USA'
  AND metric = 'Pharmaceutical R&D expenditure'
  AND unit = 'USD million'
  AND period = '2024';
-- 预期：75895 USD million
```

### 第五幕：发布并查询

1. 审核验证结果、指标定义及文档来源。
2. 输入自己的姓名和审核说明，创建 `v1.0` 审核版本。
3. 发布版本，打开 **Playground** 并选择它。
4. 首次演示建议使用 **Saved metrics**。
5. 再尝试自然语言，执行前检查解释结果。

| 问题 | Saved metric | 预期结果 |
| --- | --- | --- |
| How many reviewed observations are available? | `reviewed_observation_count` | 9 |
| What is the US share of new-medicine sales for 2020–2024 launches? | `us_new_medicine_sales_share_percent` | 74.1% |
| What was pharmaceutical R&D expenditure in the USA in 2024, in USD million? | `us_rd_2024_usd_million` | 75895 USD million |
| What was pharmaceutical R&D expenditure in Europe in 2024, in EUR million? | `europe_rd_2024_eur_million` | 56344 EUR million |

讲解：

> PDF 是原始证据。
> 我审核了提取数据，并保留单位、时期和页码。
> SQL 验证指标计算，发布冻结已经审核的语义版本。
> Playground 按该版本查询这些结构化数据行。

## 非结构化数据需要参考 SQL 吗？

| 对象 | 当前要求 | 检查内容 |
| --- | --- | --- |
| PDF 或支持性段落 | 不需要参考 SQL | 人工检查原文及关联含义 |
| 文档与已有模型的证据关联 | 关联本身不需要 SQL | 审核目标和范围；已有指标仍需 SQL |
| 从图表转出的数值指标 | 发布前每个指标需要参考 SQL | 比较编译结果和直接查询结果 |
| 图表提取准确性 | 必须对照原页审核 | 核对数值、标签、单位、日期和人群 |

参考 SQL 是当前发布流程的要求，不是所有非结构化文档的固有要求。
SQL 只能对账已存储的数据，不能证明 OCR 或图表提取正确。
将来可以辅助生成参考查询以减少输入，但仍需独立审核。
本次准备没有增加该自动化功能。

## 演示边界

- 审核姓名、备注及确认操作必须来自实际审核者。
- 随时可在最新修订中重新分析页面。系统创建新修订，并保留先前审核和模型关联。
- 故事一附加证据，不增加数值事实表。
- 故事二创建独立数据源，不合并进原制药情报模型。
- 自然语言解释取决于模型，Saved metrics 是可重复的演示路径。
- Playground 可以回答已发布模型的关联文档问题。同一模型可以联合使用一项 SQL 指标和文档证据。跨模型问答及自动汇率换算仍未实现。
- [准备验证记录](pharma-demo-stories-verification.json)区分确定性检查与在线 AI 行为。

两条故事均通过隔离环境中的验证、发布及 Saved metrics 执行检查。
故事一覆盖六个指标，故事二覆盖十个指标，相关回归测试共 83 项通过。
本次没有重新运行在线 AI 提取或自然语言解释。
