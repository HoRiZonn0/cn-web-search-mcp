# 架构与数据边界

```text
MCP tools
  → JobService
    → ResearchRunner
      → YAML SourceRegistry（全量加载与校验）
      → SourceRouter（意图定向提示）
      → Search Core
      → 360 / Sogou / Bing RSS / Web Search adapters
      → SourceAdapterRegistry
        → intent-routed catalog discovery adapters
        → Crossref / arXiv / PubMed direct API adapters
      → ContentFetcher
        → HTTP first
        → optional Firecrawl fallback
        → domain health routing
      → quality scoring and retry planning
    → SQLite + local artifacts
```

## 核心不变量

1. 每轮每个查询都尝试四个逻辑来源，失败也必须形成状态记录。
2. 每次任务完整扫描打包的权威知识库，模型不参与扫描。
3. 搜索摘要只作为候选线索；有正文的结果才可成为核心证据。
4. 截止时间在评分前执行硬过滤。
5. 是否补搜由覆盖、时效、权威性、冲突和可回答性共同决定。
6. 原始正文不进入默认 MCP 工具结果，只返回最小证据片段和 URL。
7. 抓取失败不会终止整批任务；配置 Firecrawl 后，受阻域名会自动升级抓取后端。
8. YAML 中的来源声明不等于运行能力；只有注册 Adapter 的端点才是 executable。
9. 结构化定向来源只能补充四源结果，不能替代四源完整执行。
10. 目录主页通过域名定向搜索只产生候选线索；覆盖报告不得把它计为来源自身的直接 API。

## 来源目录

运行时以 `src/cn_web_search_mcp/data/sources.yaml` 为准。服务启动时完整解析 YAML，并执行：

- 重复 YAML 键检测；
- Pydantic 字段校验；
- declared/loaded 数量一致性检查；
- 来源 ID 与端点 ID 唯一性检查；
- fallback 引用完整性检查。

`routing.yaml` 只负责生成主源、备源和核验源提示。来源健康度、响应时间和熔断状态仍保存在 SQLite，不写回静态 YAML。

`SourceAdapterRegistry` 在启动时把代码实现绑定到 YAML 的来源 ID 和端点 ID。注册的端点若不属于对应来源，服务会立即拒绝启动。运行覆盖分为：

- `executable`：来源自身的直接搜索/API 实现；
- `discovery_only`：通过共享 Web Search 后端执行 `site:domain` 定向发现，并过滤非目标域名；
- `not_implemented`：仅有目录声明，尚无可运行实现。

研究任务先完成四源搜索，再并发执行意图路由选中的来源 Adapter。一个定向来源失败只形成独立阶段记录，不影响其他来源和四源完成状态。

当前处于迁移期：旧 Markdown 保留用于无损等价测试，但线上规划已经不再直接解析 Markdown。

## 搜索来源与证据来源

每条结果区分：

- `search_channel`：四源策略中的逻辑渠道；
- `search_backend`：实际实现，例如 `searxng`；
- `upstream_engine`：SearXNG内部的 Bing、DuckDuckGo 等；
- `publisher`：正文发布网站；
- `source_role`：原始官方、二手材料或未知来源。

互证按发布者和原始信息来源判断，不能按搜索渠道数量判断。

## 任务状态

```text
queued → running → completed
                 → unresolvable
                 → failed
                 → cancelled
```

进程启动时，遗留的 `queued/running` 任务会标记为 `failed/interrupted`，避免永久停留在运行状态。每轮输入、证据包和最终结果均保存为可回放 JSON。
