# 架构与数据边界

```text
MCP tools
  → JobService
    → ResearchRunner
      → Search Core
      → 360 / Sogou / Bing RSS / Web Search adapters
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
