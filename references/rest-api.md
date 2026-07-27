# CN Web Search REST API

REST API 面向不支持 MCP 的 Agent、自动化脚本和业务服务。它只负责 HTTP 协议、鉴权和参数校验，搜索任务仍由与 MCP 相同的 `JobService`、`ResearchRunner` 和搜索 Core 执行。

## 启动

PowerShell：

```powershell
cd E:\work1_cn-web-search-skill\cn-web-search-mcp
$env:CNWS_DATA_DIR = "$PWD\.cnws-api-data"
$env:CNWS_API_HOST = "127.0.0.1"
$env:CNWS_API_PORT = "8766"
$env:CNWS_API_BEARER_TOKEN = "使用密码管理器生成的长随机值"
.\.venv\Scripts\cn-web-search-api.exe
```

Linux/macOS：

```bash
export CNWS_DATA_DIR="$PWD/.cnws-api-data"
export CNWS_API_HOST="127.0.0.1"
export CNWS_API_PORT="8766"
export CNWS_API_BEARER_TOKEN="<long-random-token>"
.venv/bin/cn-web-search-api
```

非回环监听（例如 `0.0.0.0`）时必须配置 `CNWS_API_BEARER_TOKEN`，否则服务拒绝启动。生产环境还必须由 Caddy、Nginx 或云网关提供 HTTPS；Bearer Token 不能替代传输加密。

## 异步调用

创建任务：

```http
POST /v1/research
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "question": "帮我查询最新的世界杯赛程",
  "requirements": [
    "给出剩余赛程",
    "转换为北京时间",
    "优先采用权威来源"
  ],
  "profile": "balanced",
  "max_rounds": 3,
  "cutoff_at": "2026-07-23T12:00:00+08:00",
  "timezone": "Asia/Shanghai"
}
```

服务器返回 HTTP 202：

```json
{
  "job_id": "rs_abc123",
  "status": "queued"
}
```

随后调用：

```text
GET /v1/research/rs_abc123
GET /v1/research/rs_abc123/result
```

任务未结束时，结果接口返回 HTTP 202；进入终态后返回 HTTP 200。取消尚未完成的任务：

```text
DELETE /v1/research/rs_abc123
```

未知任务统一返回 HTTP 404，参数错误返回 HTTP 422，Token 缺失或错误返回 HTTP 401。

商业实例可以查询本月使用量：

```text
GET /v1/account/usage
```

响应包含套餐、月度额度、已用/剩余积分、不同 profile 的任务数、当前活跃任务和限流参数。

## 同步便捷接口

```text
POST /v1/research/sync
```

请求结构与异步接口相同。服务最多等待 `CNWS_API_SYNC_TIMEOUT_SECONDS`（默认 120 秒）。在期限内完成则直接返回终态结果；超时则返回 HTTP 202 和 `job_id`，调用方必须切换到异步轮询。

完整搜索可能持续数分钟，生产 Agent 应优先使用异步接口。

## Agent 调用约定

推荐的工具工作流：

1. 使用用户原始问题调用 `POST /v1/research`。
2. 在后台静默轮询状态，不向最终用户输出搜索进度。
3. 任务进入终态后读取 `/result`。
4. 只根据 `result.answer_context.facts` 中带 URL 的事实回答。
5. 明确披露 `conflicts` 和 `unresolved`，不要根据搜索摘要补写事实。
6. 可使用 `result.quality` 判断是否需要提示用户证据不足。

OpenAPI 工具描述可直接从以下地址获取：

```text
http://127.0.0.1:8766/openapi.json
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `CNWS_API_HOST` | `127.0.0.1` | REST API 监听地址 |
| `CNWS_API_PORT` | `8766` | REST API 监听端口 |
| `CNWS_API_BEARER_TOKEN` | 空 | API Token；非回环监听时强制要求 |
| `CNWS_API_SYNC_TIMEOUT_SECONDS` | `120` | 同步接口最大等待秒数 |
| `CNWS_DATA_DIR` | `~/.cn-web-search-mcp` | 任务、缓存和证据目录 |
| `CNWS_COMMERCIAL_MODE` | `false` | 启用单客户商业实例 |
| `CNWS_CUSTOMER_ID` | `local` | 实例客户标识 |
| `CNWS_CUSTOMER_PLAN` | `developer` | 套餐名称 |
| `CNWS_MONTHLY_CREDIT_QUOTA` | `0` | 月度积分 |
| `CNWS_RATE_LIMIT_PER_MINUTE` | `0` | 每分钟任务创建限制 |
| `CNWS_MAX_ACTIVE_JOBS` | `0` | 最大活跃任务数 |

搜索代理、SearXNG、Firecrawl、超时和抓取限制等配置与 MCP 完全相同。

商业模式下 API Key、月度额度、每分钟限流和最大活跃任务数都必须显式配置为有效值。参见 [`commercial-mvp.md`](commercial-mvp.md)。

## MCP 与 REST 同时运行

两个协议共享代码，但默认命令会启动两个独立进程。当前 `JobStore` 在进程启动时会把遗留的 `queued/running` 任务标记为中断，因此两个进程不能同时指向同一个数据目录。

并行运行时分别配置：

```powershell
# MCP 进程
$env:CNWS_DATA_DIR = "$PWD\.cnws-mcp-data"

# REST 进程（在另一个终端）
$env:CNWS_DATA_DIR = "$PWD\.cnws-api-data"
```

这不会造成搜索逻辑分叉，只是隔离两个进程的任务状态和缓存。后续若增加统一 ASGI 宿主或多进程任务队列，再迁移到共享任务存储。
