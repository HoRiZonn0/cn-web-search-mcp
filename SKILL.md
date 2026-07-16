---
name: cn-web-search-mcp
description: 通过 CN Web Search MCP 自主完成中文联网搜索、最新信息查询、事实核验、资料调研、政策新闻、产品对比和外部知识补充。服务内部执行权威知识库完整扫描、四源搜索、正文抓取、证据评分和按缺口补搜；当回答依赖当前或外部网页信息时使用。
---

# CN Web Search MCP

将搜索流程交给 MCP 服务，不要自行编排搜索节点或读取内部知识库。

1. 调用 `research_start`，传入用户原始问题；复杂问题将必需信息放入 `requirements`。
2. 静默调用 `research_status`，直到状态为 `completed`、`unresolvable`、`failed` 或 `cancelled`。不要向用户输出轮次、节点、抓取等中间进度。
3. 完成后调用 `research_result`。只使用 `answer_context.facts` 和 `evidence` 中有明确 URL 的内容回答。
4. 对实时信息标明 `observed_at` 或 `published_at`。不得把检索时间当成信息发布时间。
5. 明确披露 `unresolved` 和未解决冲突，不得用常识补写缺失事实。
6. 每个关键事实就近附来源 URL，避免把搜索渠道当作原始发布方。

服务异常时报告错误，不要绕过 MCP 降级为未经控制的搜索流程。

部署和环境变量见 [MCP 配置](references/mcp-setup.md)。
