# Agent Studio 通过 MCP 查询财务数据

[English guide and tool arguments](semantic-hub-agent-studio-workflow.md)

本指南以 Finance sample 为主演示。
建议先使用一个智能体，完成已发布指标的发现、解析、编译和样本查询。
具体界面字段取决于已安装的 Agent Studio 版本。

```text
用户问题 -> Agent Studio 智能体 -> MCP stdio 适配器
                                      |
                              已部署消费者 HTTP API
                                      |
                      已发布定义 -> 范围检查 -> 编译 -> 样本查询
```

## 1. 发布财务模型

1. 打开 Finance sample 的 Studio。
2. 检查 `total_amount_sgd` 的定义、单位和数据范围。
3. 添加以下独立校验 SQL，然后保存并验证。
4. 审阅定义和证据，创建审阅版本，然后发布。
5. 如需文档问答，将审阅后的 MAS 段落包含在该发布版本中。

```sql
SELECT SUM(amount_sgd) AS total_amount_sgd
FROM transactions
WHERE status = 'SETTLED';
```

初始样本预期为 **686,572.96 SGD**，覆盖 2026 年 9 月。
指标表示已结算付款的发送方流出金额。
不要将付款表、交易表和双边账务金额重复相加。
MCP 只读取已发布模型，不能发布草稿。
详细发布流程见[财务演示说明](finance-customer-demo-story.md)。

## 2. 注册 MCP

1. 导入 [MCP 配置](../apps/semantic-hub-mcp/agent-studio.mcp.json)。
2. 将 `SEMANTIC_HUB_URL` 设置为以下地址。
3. 在每个 MCP 实例的用户环境参数中明确配置 `CDSW_APIV2_KEY`。
   替换配置中的占位符。不要假定 Agent Studio 会传递运行环境密钥。
   填入实际密钥，不加 `Bearer ` 前缀；如有密钥字段，请使用该字段。
4. 清除旧的 `SEMANTIC_HUB_API_TOKEN`，因为它的优先级更高。
5. 发现全部 12 个工具，并调用 `hub_status`。

```text
https://semantic-hub-acpkiu.ml-c99c87a0-2d3.qzhong-a.a465-9q4k.cloudera.site
```

URL 不包含 `/api/semantic-hub/v1`。
该适配器使用 stdio。应用地址不是 HTTP MCP 端点。
配置通过 `uvx --refresh --from` 安装 GitHub `main` 分支中的 MCP 包。
启动时刷新包缓存。
具体命令见[英文指南](semantic-hub-agent-studio-workflow.md#2-register-mcp-and-verify-discovery)。
不要将密钥写入提示词或导出配置。
浏览器登录态不会自动提供 MCP 凭据。

## 3. 创建智能体

1. 创建 `Finance Query Assistant` 对话工作流。
2. 添加支持工具调用的智能体。
3. 为其分配 `semantic-hub` 的全部 12 个只读工具。
4. 粘贴 [finance-query-assistant.txt](agent-studio/finance-query-assistant.txt)。
5. 使用部署中可用的工具调用模型。

如需管理智能体和两个专家，请使用[完整智能体定义](semantic-hub-agent-studio-workflow.md#3-configure-the-conversation)。
该章节包含每个智能体的配置字段、工具分配、Backstory 和 Goal。
简短演示无需增加委派步骤。

## 4. 执行查询

1. 调用 `list_semantic_models`，参数为 `q="finance"`。
2. 如果目录为空，停止查询并完成模型发布。
3. 读取模型、已发布版本、定义和血缘。
4. 保留返回的 `model_id`、`version` 和 `context_sha256`。
5. 使用原始问题调用 `resolve_semantic_context`，选择已发现的指标。
6. 仅在返回 `ready` 时保留其 `bundle_id` 并继续。
7. 调用 `inspect_metric_coverage`，检查时间覆盖。
8. 单独检查发送方角色、已结算范围、SGD 单位和汇总口径。
9. 携带相同版本、上下文包和原始问题调用 `compile_semantic_query`。
10. 检查返回 SQL，并仅在编译状态为 `ready` 时执行 `query_sample_data`。
11. 仅依据 `answered` 状态和实际返回行回答数值。

每次查询只选一个指标，且 `limit <= 100`。
分组或筛选字段应先加入解析请求的 `required_fields`。
具体 JSON 参数见[英文查询步骤](semantic-hub-agent-studio-workflow.md#5-run-the-finance-conversation)。
每个新问题都要重新解析上下文包。
上下文包当前有效期为 300 秒，以 `hub_status` 为准。
版本冲突或上下文过期时，重新发现并解析。

## 5. 演示问题

以下数字为初始样本预期，不能替代实际工具结果。

| 问题 | 应有行为 |
| --- | --- |
| What is the total settled sender outflow in SGD for the sample? | 编译并执行；仅在实际返回时回答 686,572.96 SGD。 |
| Show total settled sender outflow in SGD by sender jurisdiction. | 检查发送方维度；预期 GB 44,454.90、HK 350,641.68、SG 291,476.38 SGD。 |
| What is total settled sender outflow in SGD for sender jurisdiction SG? | 使用已审阅的发送方筛选；预期 291,476.38 SGD。 |
| What was the total settled sender outflow in SGD in 2025? | 报告缺少该时期数据，不复用 2026 年结果。 |
| Include rejected transfers in total_amount_sgd. | 保留已发布的已结算范围，不扩大指标定义。 |
| What is the total for last month? | 先澄清时期和指标。 |

可单独追加文档问题：

> According to the attached MAS announcement, how does SG QR support PayNow transfers?

使用 `get_published_documents` 读取相同版本的已发布段落。
[MAS 单页摘录](demo-inputs/finance-real/mas-sgqr-media-release-2017-11-20-page-1-excerpt.pdf)需要先审阅、关联并发布。
上传文件本身不会使其成为 MCP 证据。
该历史公告不能证明样本付款使用 SG QR，也不能认证样本总额或汇率。
引用实际返回的文档标识、修订和页码。

回答应包含实际结果、范围、证据类型、模型版本和限制。
说明查询使用合成样本数据。
仅编译 SQL 不等于执行成功。
空结果、错误和无覆盖都不等于零。

## 6. 验证状态与验收

2026 年 10 月 19 日，实际 MCP stdio 客户端已通过 CAI 认证访问部署 API。
工具发现返回全部 12 个工具。
`hub_status`、模型列表和关键词搜索调用成功。
但已发布目录返回 `items=[]` 和 `total=0`，搜索没有匹配结果。
因此财务模型的解析、覆盖检查、编译和执行尚未在该部署完成。
该记录不代表实际 Agent Studio 托管工作流已通过验收。

1. 发布财务模型后，从 Agent Studio 运行上述六个问题。
2. 保存模型版本、哈希、上下文包、SQL、状态和实际结果。
3. 测试错误哈希、上下文过期和文档证据缺失。
4. 将实际结果与样本预期分别记录。

标准 `check_live.py` 依赖制药模型，不应直接作为财务验收脚本。

| 问题 | 处理方法 |
| --- | --- |
| 登录页面、重定向、401 或 403 | 检查 MCP 子进程的 CAI 密钥。 |
| 模型列表为空 | 发布已审阅模型，确认使用相同应用地址。 |
| 工具缺失 | 检查安装提交、入口和发现缓存。 |
| 版本冲突 | 重新发现版本并解析上下文。 |
| 样本执行不可用 | 说明限制；仅展示编译结果。 |
| 文档段落缺失 | 检查该段落是否属于所选发布版本。 |
