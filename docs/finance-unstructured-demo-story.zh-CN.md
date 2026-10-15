# 合成金融数据：文档证据演示

准备日期：2026 年 10 月 14 日。[完整英文操作说明](finance-unstructured-demo-story.md)。

合成金融 PDF 和图表已按用户要求从文档库移除。本页保留为历史演示说明。
当前演示请使用已上传的 [HSBC 原始文档](finance-real-document-sources.md)。
现有金融草稿、发布版本和原始数据均未修改。这些材料完全来自合成数据，不是真实客户资料。

## 材料内容

打开 [金融证据 PDF](demo-inputs/finance/synthetic-finance-supporting-evidence.pdf)。

| 页码 | 内容 | 作用 |
| --- | --- | --- |
| 1 | 已结算付款定义、借贷记账说明 | 解释指标口径，防止重复计算 |
| 2 | 固定汇率与舍入规则 | 解释 SGD 金额如何形成 |
| 3 | GB、HK、SG 金额图片图表 | 演示 AI 识图和人工核对 |
| 4 | SYN-T00000000 结算备忘录 | 将文档描述对应到具体交易 |

```text
金融 CSV → 文档与图表 → 分析并检查
                            ├→ 关联现有模型 → 验证并发布 → 查询
                            └→ 审核图表行 → 创建独立模型 → 验证并发布
```

## 故事一：让现有金融模型带上业务解释

讲解：“结构化数据给出金额。文档解释哪些金额可以计算，以及换算规则是什么。”

1. 打开 [Supporting materials](http://localhost:8084/demo/materials?source=finance)。
2. 选择 `synthetic-finance-supporting-evidence`，无需重复上传。
3. 展开 **Extracted sections**，检查第 1、2、4 页。
4. 可点击 **Analyze content**，查看 AI 总结与引用。
5. 展开 **Add evidence to an existing semantic model**。
6. 将 **Evidence to match** 设为 **All extracted document text**。
7. 暂不启用 embedding，点击 **Find model links**。
8. 展开候选列表，将模型筛选为 **Finance sample context**。
9. 搜索并核对下表中的三个候选链接。

| 搜索内容 | 页码 | 核对重点 |
| --- | --- | --- |
| `ledger_postings.amount_sgd` | page 1 | 借贷相抵为零；绝对值合计会重复计算 |
| `fx_rates.sgd_rate` | page 2 | 先逐笔换汇和舍入，再汇总 |
| `payments.amount_sgd` | page 4 | 496.90 SGD 对应已有付款，不是新增交易 |

选择原始文本 `page N` 候选即可，不必同时选择 AI 转录副本。
这些是字段级证据关联，也可以支持发布后的文档问答，无需强行关联指标。

10. 填写审核人和说明，点击 **Approve selected links**。
11. 选中已批准链接，将目标模型设为金融模型。
12. 点击 **Apply approved evidence to draft**，然后打开 Studio。
13. 为 `total_amount_sgd` 填写以下验证 SQL。
14. 保存、验证、审核，再创建并发布新版本。

```sql
SELECT SUM(amount_sgd) AS total_amount_sgd
FROM transactions
WHERE status = 'SETTLED';
```

指标读取 `payments`，验证 SQL 读取对应的已结算 `transactions`。
预期合计为 **686,572.96 SGD**，包含 **4,850 笔**已结算付款。
时间范围为 **2026 年 9 月 1–30 日，UTC**。

## Playground 演示

1. 选择刚发布的版本。
2. 使用 **Saved metrics → total_amount_sgd**，显示 686,572.96 SGD。
3. 输入 `What fixed USD-to-SGD conversion rate does this synthetic fixture use?`。
4. 点击 **Interpret question**，检查计划，再运行。
5. 预期回答为 **1 USD = 1.300000 SGD**，并引用文档。

上述指标执行与英文汇率问答已测试。中文自由提问未在本次准备中在线验证。
可继续询问为什么不能同时累计借贷两侧，或结算备忘录中的金额。

当前限制：金融组合问题在测试中触发了多条关联路径的澄清提示。
本次演示请分开执行指标与文档问题。不要将金融组合查询描述为已验证功能。

## 故事二：从图片创建独立模型

1. 分析 PDF 第 **3** 页，或分析[独立 PNG](demo-inputs/finance/finance-settled-outflow-chart.png)第 **1** 页。
2. 核对三行数值、地区、SGD 单位和 2026 年 9 月时间范围。
3. 选择已核对行，展开创建草稿模型区域。
4. 输入名称 `Synthetic settled outflow by jurisdiction`、审核人、说明，并确认。
5. 点击 **Approve rows and create model**，再到 Studio 验证和发布。

| 付款方地区 | 金额 SGD |
| --- | ---: |
| GB | 44,454.90 |
| HK | 350,641.68 |
| SG | 291,476.38 |

PDF 与 PNG 表达相同事实，只需使用其中一个创建模型。
本次 GPT-4o 在线测试正确提取了 PDF 第 3 页的三行金额、SGD 单位、地区和月份。
这是独立的聚合数据副本，不能与原始付款金额再次累加。
新模型的验证 SQL 需根据实际审核后的指标名和观察记录 ID 准备。

原始值核对文件：[三行核对表](demo-inputs/finance/finance-chart-row-guide.csv)、[原始付款分组 SQL](demo-inputs/finance/finance-chart-reference.sql)。
