> 本地模式更新（2026-10-15）：使用 `--local-no-auth --host 127.0.0.1 --port 8096` 启动消费者 API。
> 本地令牌已删除，MCP 仅需设置 `SEMANTIC_HUB_URL`。Swagger 自动加载。
> CAI `cdsw_v2_key` 验证将在 AMP 部署阶段实现，目前未实现。

# Semantic Hub 外部智能体演示工作流

[English configuration](semantic-hub-agent-studio-workflow.md)

本指南提供可粘贴的 CAI Agent Studio 配置和智能体提示词。
当前交付不代表已创建、导入或验证远程 CAI 工作流。
本指南没有虚构 Agent Studio 的 JSON 导入格式。
具体界面字段取决于部署版本。

外部智能体负责自然语言理解和任务规划。
Semantic Hub 提供已发布语义、文档证据、受控查询编译和可选样本执行。
工作流不调用 Helios Playground 或内部 LLM Harness。

```text
用户问题
   |
   v
对话管理智能体
   +--> 语义上下文专家 --> 已发布定义、覆盖范围、上下文包
   +--> 查询与证据专家 --> 查询编译、样本结果、已发布文档
                              |
                              v
                      Semantic Hub MCP --> 只读后端 API
```

## 1. 准备后端和网络

1. 选择已发布的制药行业模型。
2. 检查指标定义和样本数据。
3. 如需文档对比演示，发布经过审阅的第 14 页证据。
4. 使用与编辑应用相同的状态目录启动只读 API。
5. 确保 CAI 的 MCP 运行主机可以访问该 API。

```sh
python start_semantic_hub_api.py \
  --state-dir <编辑应用使用的状态目录> \
  --local-no-auth --host 127.0.0.1 --port 8096
```

编辑界面继续使用本地 8084 端口。
本地无认证模式仅绑定环回地址。CAI 部署入口与身份验证将在 AMP 阶段配置。
远程 CAI 的 `localhost` 不指向开发者电脑。
浏览器登录态不会自动传递给 MCP。

为 MCP 配置以下环境变量：

```text
SEMANTIC_HUB_URL=https://<CAI可访问的后端域名>
```

URL 只包含服务器源地址，不包含 `/api/semantic-hub/v1`。
MCP 自动添加 API 前缀。
本地模式没有企业级用户授权或租户隔离。
不要将凭据写入提示词或工作流导出文件。

本机准备的验证地址为 `http://127.0.0.1:8096`，因为本机 8086 端口已被占用。
状态目录为 `/tmp/helios-builder-review`。
本地 API 凭据文件已删除，不再需要消费者令牌。
复现该本地运行环境时，请使用 `--port 8096`。
这些本地路径不代表远程 CAI 已能访问该服务。
独立 API 进程可使用 `--model-token-file ~/tokens/openai` 加载已配置 embedding 服务的凭据。
该参数不启用 API 内部自然语言查询规划。
缺少可用服务凭据时，明确请求 embedding 搜索应返回不可用。

## 2. 注册 MCP

1. 按 [MCP 包说明](../apps/semantic-hub-mcp/)安装并启动适配器。
2. 确认远程安装版本已经包含该包。
3. 固定经过审阅的提交或发行版本。
4. 注册下面两个工具实例，或使用平台的逐智能体工具选择。
5. 在实际 CAI 运行环境中验证全部 12 个工具。

| 实例 | 智能体 | 工具 |
| --- | --- | --- |
| `semantic-context` | 语义上下文专家 | `hub_status`, `list_semantic_models`, `get_semantic_model`, `list_model_versions`, `get_model_version`, `search_semantics`, `resolve_semantic_context`, `inspect_metric_coverage`, `get_model_lineage`, `get_published_documents` |
| `semantic-query` | 查询与证据专家 | `compile_semantic_query`, `query_sample_data`, `get_published_documents` |

所有工具均为只读操作。
导入 [GitHub MCP 配置](../apps/semantic-hub-mcp/agent-studio.mcp.json)。
启动命令为 `uvx`；参数通过 `--from` 指定 GitHub 仓库中的 MCP 包。
演示时将 `@main` 替换为经过测试的提交 SHA。
本地配置只需 API 地址。
该包使用 stdio，不提供 HTTP MCP 服务地址。
部分只读操作使用 HTTP POST。
参数应遵循实际发现的工具 schema。
精确 HTTP 路径见后端 OpenAPI 和 MCP 包。

搜索结果应明确区分关键词搜索和 embedding 搜索。
Embedding 搜索需要配置对应客户端。
明确请求 embedding 时，配置或服务失败应直接返回错误，不应静默改用关键词。

## 3. 配置智能体

1. 创建 `Semantic Hub Query Assistant` 对话工作流。
2. 如果平台支持，选择分层委派模式。
3. 添加一个管理智能体和两个专家。
4. 按下表分配工具和提示词。
5. 使用当前部署中可用且支持工具调用的模型。
6. 如果模型支持，可从 `0.1` 温度开始。

| 智能体 | 委派 | MCP | 可直接使用的提示词 |
| --- | --- | --- | --- |
| 对话管理智能体 | 开启 | 无 | [manager.txt](agent-studio/manager.txt) |
| 语义上下文专家 | 关闭 | `semantic-context` | [semantic-context-specialist.txt](agent-studio/semantic-context-specialist.txt) |
| 查询与证据专家 | 关闭 | `semantic-query` | [query-evidence-specialist.txt](agent-studio/query-evidence-specialist.txt) |

提示词使用英文，便于直接复用。
没有分层委派功能时，可由单个智能体执行同一顺序。

## 4. 固定语义版本

1. 发现目标模型和已发布版本。
2. 从版本响应获取 `model_id`、`version` 和 `context_sha256`。
3. 发现阶段之后，每次调用都携带完整版本标识。
4. 使用原始问题调用 `resolve_semantic_context`。
5. 原样保存返回的 `bundle_id`。
6. 使用 `inspect_metric_coverage` 检查实际数据覆盖。
7. 将相同版本、上下文包和原始问题传给查询专家。
8. 如发生版本冲突，停止查询并重新解析上下文。

每次受控查询只选择一个指标。
维度和筛选条件必须符合工具定义，且 `limit <= 100`。
上市队列、观测年份、地域、人群和单位必须分别检查。
固定 USA 人群的指标不能通过地域筛选变成韩国指标。
存在日期字段不代表存在用户要求的日期覆盖。

查询编译不代表执行成功。
`query_sample_data` 仅查询受限样本，不连接实时企业仓库。
DuckDB 不可用时，应报告执行不可用。
空结果、错误和无覆盖不能解释为零。
保留 `no_data` 和 `unsupported_scope` 等实际返回状态。

可执行以下本地检查：

```sh
python -m pip install -e './apps/semantic-hub-mcp[test]'
python -m pytest apps/semantic-hub-mcp/tests -q
```

## 5. 演示问题和验收结果

以下数字是演示预期，回答仍须依据工具实际返回的证据。
模型 ID、版本、哈希和上下文包都应从运行中的后端获取。
发布前置步骤见[制药演示故事](pharma-intelligence-demo-story.zh-CN.md)。

| 用户问题 | 应有行为 |
| --- | --- |
| 2020–2024 年上市新药的美国销售占比是多少？ | 检查覆盖后编译并执行样本查询。仅在实际返回时回答 74.1%。说明销售观测年份为 2025。 |
| 1999–2020 年上市新药的美国销售占比是多少？ | 报告上市队列无覆盖，不复用 74.1%，不外推，不回答零。 |
| 同一上市队列的韩国销售占比是多少？ | 不使用固定 USA 指标。查找支持韩国的指标，否则报告无覆盖。 |
| 2025 年北美占整个处方药市场的比例是多少？ | 读取同一已发布版本的第 14 页证据。仅在实际存在对应段落时回答 54.7%。 |
| 2020–2024 年北美处方药市场占比是多少？ | 请求澄清或报告无覆盖。2025 年观测不能回答该时期。 |
| 比较美国新药销售占比和北美整体处方药市场占比。 | 分别呈现样本 SQL 结果与文档陈述，保留地域、人群和时间口径差异。 |

第 14 页的北美包括 USA 和 Canada。
其范围为零售和医院处方药市场，采用出厂价格。
上传或草稿附件不足以支持回答；证据必须属于当前已发布版本。

建议回答格式：

```text
答案：<实际结果、澄清问题或不可用说明>
范围：<地域；人群；上市队列；观测时间；单位>
证据类型：<已执行样本指标 / 仅编译查询 / 已发布文档段落>
来源：<模型版本和指标，或文档修订和页码>
限制：<样本执行、覆盖缺失、证据缺失等实际限制>
```

## 6. 验证与排错

1. 运行包说明中的测试和后端契约检查。
2. 从实际 CAI 运行主机检查 MCP 工具发现。
3. 对选定已发布版本执行上表六个问题。
4. 保存版本、哈希、上下文包、执行状态和引用。
5. 使用错误哈希验证后端拒绝行为。
6. 验证样本执行不可用和文档证据缺失两种情况。
7. 在记录中分别标注本地测试和远程 CAI 测试。

| 问题 | 处理方法 |
| --- | --- |
| 后端不可达 | 从 MCP 运行主机检查网络，确认没有误用开发机 localhost。 |
| 返回登录 HTML、重定向或 401/403 | 检查入口和 API 的机器凭据。 |
| 工具缺失 | 检查安装提交、启动入口和工具发现缓存。 |
| 版本冲突 | 重新发现已发布版本并生成上下文包，不静默切换版本。 |
| 第 14 页段落缺失 | 检查附件是否属于该已发布版本，不引用其他版本或草稿。 |
| 样本执行不可用 | 只展示编译结果，不声称计算得到答案。 |

当前配置指南不包含远程执行通过的证据。
只有实际验收记录才能支持“CAI 集成已验证”的结论。
