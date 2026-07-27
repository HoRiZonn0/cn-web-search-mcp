# CN Web Search MCP 配置

## 目录

- [安装](#安装)
- [接入 OpenClaw](#接入-openclaw)
- [搜索后端](#搜索后端)
- [Streamable HTTP](#streamable-http)
- [标准 REST API](rest-api.md)
- [环境变量](#环境变量)
- [安全边界](#安全边界)
- [验证](#验证)

## 安装

要求 Python 3.11 或更高版本。项目使用官方 MCP Python SDK 1.x，并暂时限制 `<2`，避免 2.x 预发布阶段的破坏性变化。

PowerShell：

```powershell
cd E:\work1_cn-web-search-skill\cn-web-search-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

也可以执行：

```powershell
.\scripts\install.ps1
```

## 接入 OpenClaw

推荐使用 stdio，由 OpenClaw 管理 MCP 子进程。将路径替换为实际绝对路径：

```powershell
openclaw mcp add cn-web-search `
  --command "E:\work1_cn-web-search-skill\cn-web-search-mcp\.venv\Scripts\python.exe" `
  --arg -m `
  --arg cn_web_search_mcp `
  --cwd "E:\work1_cn-web-search-skill\cn-web-search-mcp" `
  --env "CNWS_DATA_DIR=E:\work1_cn-web-search-skill\cn-web-search-mcp\.cnws-data"

openclaw mcp doctor cn-web-search --probe
```

也可以用 JSON 注册：

```powershell
openclaw mcp set cn-web-search '{"command":"E:\\work1_cn-web-search-skill\\cn-web-search-mcp\\.venv\\Scripts\\python.exe","args":["-m","cn_web_search_mcp"],"cwd":"E:\\work1_cn-web-search-skill\\cn-web-search-mcp","env":{"CNWS_DATA_DIR":"E:\\work1_cn-web-search-skill\\cn-web-search-mcp\\.cnws-data"}}'
```

注册后将本目录作为 Skill 安装到 OpenClaw。Skill 只负责触发 MCP 和约束最终回答，不再让模型读取全部搜索规则。

## 搜索后端

服务始终尝试四个逻辑来源：

1. 360 HTML；
2. 搜狗 HTML；
3. Bing RSS；
4. `web_search`。

`web_search` 的默认行为：

- 配置 `CNWS_SEARXNG_ENDPOINT` 时使用 SearXNG；
- 未配置时使用 DuckDuckGo HTML。

本机 SearXNG 示例：

```powershell
$env:CNWS_SEARXNG_ENDPOINT = "http://127.0.0.1:8080"
$env:CNWS_WEB_SEARCH_BACKEND = "searxng"
$env:CNWS_SEARXNG_ENGINES = "bing,duckduckgo"
```

SearXNG 是受信任的配置端点，可以使用本机地址；普通待抓取 URL 默认禁止访问回环、内网、链路本地和其他非公网 IP。

可选 Firecrawl 正文后备：

```powershell
$env:CNWS_FIRECRAWL_ENDPOINT = "http://127.0.0.1:3002"
# 使用 Firecrawl Cloud 或需要鉴权的实例时再设置：
$env:CNWS_FIRECRAWL_API_KEY = "通过环境变量注入，不要写进仓库"
```

启用后先用低成本 HTTP 抓取；HTTP 超时、403/429、反爬页或空正文时自动调用 `/v2/scrape`。域名连续失败后，后续 URL 会优先走 Firecrawl，再以 HTTP 作为后备。

## Streamable HTTP

本机服务模式：

```powershell
.\.venv\Scripts\python.exe -m cn_web_search_mcp `
  --transport streamable-http `
  --host 127.0.0.1 `
  --port 8765
```

MCP 地址：

```text
http://127.0.0.1:8765/mcp
```

OpenClaw 注册：

```powershell
openclaw mcp set cn-web-search '{"url":"http://127.0.0.1:8765/mcp","transport":"streamable-http","timeout":30,"supportsParallelToolCalls":true}'
openclaw mcp doctor cn-web-search --probe
```

HTTP 模式当前设计为本机或受保护反向代理后的服务，不应直接暴露到公网。

监听非回环地址时，服务强制要求静态 Bearer Token：

```powershell
$env:CNWS_MCP_BEARER_TOKEN = "使用密码管理器生成的长随机值"
.\.venv\Scripts\python.exe -m cn_web_search_mcp --transport streamable-http --host 0.0.0.0 --port 8765
```

客户端请求头使用 `Authorization: Bearer <token>`。生产环境还应在前置网关启用 HTTPS；静态 Token 不能替代传输加密。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `CNWS_DATA_DIR` | `~/.cn-web-search-mcp` | SQLite、缓存和证据产物目录 |
| `CNWS_MCP_TRANSPORT` | `stdio` | `stdio` 或 `streamable-http` |
| `CNWS_MCP_HOST` | `127.0.0.1` | HTTP监听地址 |
| `CNWS_MCP_PORT` | `8765` | HTTP监听端口 |
| `CNWS_API_HOST` | `127.0.0.1` | 标准 REST API 监听地址 |
| `CNWS_API_PORT` | `8766` | 标准 REST API 监听端口 |
| `CNWS_API_BEARER_TOKEN` | 空 | REST Bearer Token；非回环监听时强制要求 |
| `CNWS_API_SYNC_TIMEOUT_SECONDS` | `120` | REST 同步接口最大等待秒数 |
| `CNWS_PROXY_URL` | 空 | 搜索和网页抓取代理 |
| `CNWS_SEARXNG_ENDPOINT` | 空 | SearXNG根地址 |
| `CNWS_SEARXNG_ENGINES` | 空 | SearXNG上游引擎列表 |
| `CNWS_WEB_SEARCH_BACKEND` | `auto` | `auto`、`searxng`、`duckduckgo` |
| `CNWS_FIRECRAWL_ENDPOINT` | 空 | 可选Firecrawl根地址或 `/v2/scrape` 地址 |
| `CNWS_FIRECRAWL_API_KEY` | 空 | 可选Firecrawl Bearer Token |
| `CNWS_FIRECRAWL_HTTP_TIMEOUT_SECONDS` | `4` | 启用Firecrawl时普通HTTP的快速后备阈值 |
| `CNWS_REQUEST_TIMEOUT_SECONDS` | `10` | 单搜索节点网络超时 |
| `CNWS_FETCH_TIMEOUT_SECONDS` | `18` | 单网页抓取超时 |
| `CNWS_MAX_RESPONSE_BYTES` | `2000000` | 单响应最大字节数 |
| `CNWS_MAX_RESULTS_PER_SOURCE` | `8` | 每来源最多候选结果 |
| `CNWS_MAX_FETCHES_PER_ROUND` | `12` | 每轮最多抓取正文数 |
| `CNWS_MAX_JOB_WORKERS` | `2` | 同时运行的研究任务数 |
| `CNWS_COMMERCIAL_MODE` | `false` | 启用单客户商业实例 |
| `CNWS_CUSTOMER_ID` | `local` | 当前实例的客户标识 |
| `CNWS_CUSTOMER_PLAN` | `developer` | 客户套餐名称 |
| `CNWS_MONTHLY_CREDIT_QUOTA` | `0` | 商业模式月度积分额度 |
| `CNWS_RATE_LIMIT_PER_MINUTE` | `0` | 商业模式每分钟任务创建限制 |
| `CNWS_MAX_ACTIVE_JOBS` | `0` | 商业模式最大活跃任务数 |
| `CNWS_CACHE_TTL_SECONDS` | `3600` | 正文缓存有效期 |
| `CNWS_ALLOW_PRIVATE_NETWORKS` | `false` | 是否允许普通网页抓取访问内网；不建议开启 |
| `CNWS_MCP_BEARER_TOKEN` | 空 | HTTP Bearer Token；非回环监听时强制要求 |

## 安全边界

- 仅允许绝对 HTTP/HTTPS URL；
- 禁止带用户名和密码的 URL；
- 默认拒绝回环、私网、链路本地和保留地址；
- 每个响应设置字节上限；
- 每轮限制抓取 URL 数量；
- 每个域名单并发并设置请求间隔；
- SQLite记录域名成功、受阻、错误比例和平均耗时，用于选择抓取后端；
- stdio 日志只写 stderr，不得污染协议 stdout；
- 原始正文和完整轨迹保存在本地，默认只向模型返回最小证据片段。

## 验证

离线单元测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

MCP协议检查：

```powershell
openclaw mcp doctor cn-web-search --probe
openclaw mcp probe cn-web-search --json
```

至少应暴露：

- `research_start`
- `research_status`
- `research_result`
- `research_cancel`

还应能够读取以下诊断资源：

- `cnws://sources/catalog`：`validation_completed` 应为 `true`；
- `cnws://sources/coverage`：检查端点是 `executable` 还是仅 `not_implemented`；
- `cnws://sources/route/{query}`：检查定向来源规划，四源策略仍应标记为独立必需流程。
