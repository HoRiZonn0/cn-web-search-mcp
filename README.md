# CN Web Search MCP

面向中文互联网研究的自主搜索 MCP 服务。它把原先依赖模型逐步执行的搜索流程收进服务端：完整扫描权威来源规则、并发执行四个逻辑搜索来源、抓取正文、筛选最小证据片段、评估搜索质量，并按信息缺口自动补搜。

当前开发版本：`0.2.0`。项目仍处于早期阶段，建议先在本机或可信网络中部署和评测。

## 主要能力

- **四源完整搜索**：每轮每个查询都尝试 360、搜狗、Bing RSS 和 `web_search`，单个来源失败不会中断整轮任务。
- **自主质量控制**：综合覆盖度、时效性、权威性、来源独立性、冲突和可回答性判断是否继续搜索。
- **正文优先**：搜索摘要只用于发现候选页面；核心事实尽量来自抓取后的正文证据。
- **缺口驱动补搜**：根据未覆盖事实、冲突和时效不足调整后续查询，而不是机械重复关键词。
- **可选抓取增强**：普通 HTTP 遇到超时、限流、反爬页或空正文时，可自动切换到 Firecrawl。
- **异步任务接口**：研究任务在后台运行，支持状态查询、结果获取和取消。
- **较小模型上下文**：完整规则库和网页正文保留在服务端，只向宿主模型返回必要事实、证据片段和 URL。
- **本地持久化**：任务、缓存、证据和域名健康信息写入 SQLite 与本地产物目录。
- **结构化来源目录**：一次性加载并校验 YAML，区分已登记来源、可执行端点和仅用于发现的入口。
- **意图定向来源**：四源搜索之外，路由选中的目录来源会通过独立的域名定向 Adapter 搜索；学术查询还可直接调用 Crossref、arXiv 与 PubMed API。

## 工作方式

```text
MCP 客户端 / Agent
  -> research_start
  -> JobService（后台任务）
    -> 完整扫描权威来源规则
    -> 查询规划与缺口分析
    -> 360 / 搜狗 / Bing RSS / web_search
    -> 按意图选择的目录来源 Adapter
       -> 来源域名定向发现
       -> Crossref / arXiv / PubMed 结构化 API
    -> 候选去重与正文抓取
       -> HTTP
       -> 可选 Firecrawl 后备
    -> 证据筛选、冲突检测与质量评分
    -> 不足时生成新查询并进入下一轮
  -> research_status
  -> research_result（事实、证据、URL、冲突与未解决项）
```

这里的“四源”表示四个必须尝试的逻辑搜索来源，不等于四个独立发布者。互证强度按正文发布者和原始信息来源判断，不能只按搜索渠道数量判断。

来源目录当前包含108个来源定义：103条由旧权威网址知识库无损迁移的条目、4个必需搜索渠道和1个新增 Crossref 来源。运行覆盖报告当前列出7个直接可执行端点，并单独列出目录来源的 `discovery_only` 入口。发现入口会生成 `site:domain` 定向查询并过滤非目标域名结果，但不能冒充来源自身 API 或直接事实证据。

## 快速开始

要求 Python 3.11 或更高版本。

### Windows PowerShell

```powershell
git clone git@github.com:HoRiZonn0/cn-web-search-mcp.git
cd cn-web-search-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

启动 stdio MCP 服务：

```powershell
.\.venv\Scripts\python.exe -m cn_web_search_mcp
```

### Linux / macOS

```bash
git clone git@github.com:HoRiZonn0/cn-web-search-mcp.git
cd cn-web-search-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m cn_web_search_mcp
```

## 接入 OpenClaw

推荐使用 stdio，让 OpenClaw 管理 MCP 子进程。将示例中的路径替换为本机绝对路径：

```powershell
openclaw mcp add cn-web-search `
  --command "<项目目录>\.venv\Scripts\python.exe" `
  --arg -m `
  --arg cn_web_search_mcp `
  --cwd "<项目目录>" `
  --env "CNWS_DATA_DIR=<项目目录>\.cnws-data"

openclaw mcp doctor cn-web-search --probe
```

随后将本仓库作为 Skill 安装到 OpenClaw。根目录的 `SKILL.md` 只负责触发 MCP、静默等待任务和约束最终回答；搜索规则与正文不会反复加入模型上下文。

更完整的安装、JSON 注册和 HTTP 接入示例见 [`references/mcp-setup.md`](references/mcp-setup.md)。

## MCP 工具

| 工具 | 用途 |
|---|---|
| `research_start` | 提交问题及可选要求，返回后台任务 ID |
| `research_status` | 查询任务状态和有限进度信息 |
| `research_result` | 获取事实、证据、来源 URL、冲突和未解决项 |
| `research_cancel` | 请求取消尚未结束的任务 |

诊断资源：

| URI | 用途 |
|---|---|
| `cnws://sources/catalog` | 查看目录版本、加载数量、完整性和哈希 |
| `cnws://sources/coverage` | 区分 declared、executable 和 not_implemented 端点 |
| `cnws://sources/route/{query}` | 预览意图定向来源；不改变四源完整策略 |

推荐调用流程：

1. 使用用户原始问题调用 `research_start`。
2. 静默轮询 `research_status`，直到进入终态。
3. 使用 `research_result` 获取证据包。
4. 最终回答只采用带明确 URL 的事实，并披露冲突和未解决项。

任务状态为：

```text
queued -> running -> completed
                  -> unresolvable
                  -> failed
                  -> cancelled
```

## 搜索后端

服务始终尝试以下四个逻辑来源：

1. 360 HTML；
2. 搜狗 HTML；
3. Bing RSS；
4. `web_search`。

四源用于开放网页发现。YAML 目录中的来源属于附加通道，只在匹配意图时执行，不会替代或跳过其中任何一源。每个被选来源都有独立 Adapter 实例：普通目录来源通过共享 Web Search 后端生成域名限定查询，并再次按域名过滤结果；存在公开结构化接口的来源优先增加直接 API Adapter。

当前学术类问题可直接路由到：

- Crossref Works API；
- arXiv Query API；
- PubMed E-utilities（ESearch + ESummary）。

`cnws://sources/coverage` 将能力分为：`executable`（直接运行端点）、`discovery_only`（借助搜索后端发现该站内容）和 `not_implemented`（尚无运行实现）。

`web_search` 默认自动选择后端：配置 `CNWS_SEARXNG_ENDPOINT` 时使用 SearXNG，否则使用 DuckDuckGo HTML。

使用本机 SearXNG：

```powershell
$env:CNWS_SEARXNG_ENDPOINT = "http://127.0.0.1:8080"
$env:CNWS_WEB_SEARCH_BACKEND = "searxng"
$env:CNWS_SEARXNG_ENGINES = "bing,duckduckgo"
```

未配置 SearXNG 时无需搜索 API，但 DuckDuckGo HTML 可能因网络环境、限流或页面变化而不可用。SearXNG 的具体上游引擎是否需要 API Key，取决于该实例启用的引擎配置。

## 可选 Firecrawl 后备

```powershell
$env:CNWS_FIRECRAWL_ENDPOINT = "http://127.0.0.1:3002"
# 仅在实例需要鉴权时设置：
$env:CNWS_FIRECRAWL_API_KEY = "<token>"
```

启用后，服务先尝试低成本 HTTP 抓取；遇到超时、`403`、`429`、反爬页或空正文时调用 Firecrawl。某个域名连续失败后，域名健康路由会让后续 URL 优先尝试 Firecrawl。

Firecrawl 是抓取后备，不会保证绕过所有登录墙、验证码或高级反自动化机制。

## Streamable HTTP

本机启动：

```powershell
.\.venv\Scripts\python.exe -m cn_web_search_mcp `
  --transport streamable-http `
  --host 127.0.0.1 `
  --port 8765
```

MCP 地址为 `http://127.0.0.1:8765/mcp`。

监听非回环地址时必须设置 Bearer Token：

```powershell
$env:CNWS_MCP_BEARER_TOKEN = "<长随机值>"
.\.venv\Scripts\python.exe -m cn_web_search_mcp `
  --transport streamable-http `
  --host 0.0.0.0 `
  --port 8765
```

生产环境还应通过可信网关启用 HTTPS。静态 Token 不能替代传输加密，不建议将服务直接暴露到公网。

## 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `CNWS_DATA_DIR` | `~/.cn-web-search-mcp` | SQLite、缓存和证据产物目录 |
| `CNWS_PROXY_URL` | 空 | 搜索和网页抓取代理 |
| `CNWS_SEARXNG_ENDPOINT` | 空 | SearXNG 根地址 |
| `CNWS_SEARXNG_ENGINES` | 空 | SearXNG 上游引擎列表 |
| `CNWS_WEB_SEARCH_BACKEND` | `auto` | `auto`、`searxng` 或 `duckduckgo` |
| `CNWS_FIRECRAWL_ENDPOINT` | 空 | Firecrawl 根地址或 `/v2/scrape` 地址 |
| `CNWS_FIRECRAWL_API_KEY` | 空 | Firecrawl Bearer Token |
| `CNWS_REQUEST_TIMEOUT_SECONDS` | `10` | 单个搜索来源的网络超时 |
| `CNWS_FETCH_TIMEOUT_SECONDS` | `18` | 单网页抓取超时 |
| `CNWS_MAX_RESULTS_PER_SOURCE` | `8` | 每个来源最多保留的候选数 |
| `CNWS_MAX_FETCHES_PER_ROUND` | `12` | 每轮最多抓取的正文数 |
| `CNWS_MAX_JOB_WORKERS` | `2` | 同时运行的研究任务数 |
| `CNWS_CACHE_TTL_SECONDS` | `3600` | 正文缓存有效期（秒） |
| `CNWS_ALLOW_PRIVATE_NETWORKS` | `false` | 是否允许普通正文抓取访问内网，不建议开启 |
| `CNWS_MCP_BEARER_TOKEN` | 空 | 非回环 HTTP 监听时强制要求 |

全部配置项见 [`references/mcp-setup.md`](references/mcp-setup.md)。

## 安全设计

- 普通抓取只接受绝对 HTTP/HTTPS URL；
- 拒绝带用户名或密码的 URL；
- 默认拒绝回环、私网、链路本地和保留地址；
- 限制单响应字节数、每轮正文数量及抓取并发；
- 对单域名实施并发和请求间隔限制；
- stdio 模式的日志只写入 stderr，避免污染 MCP 协议输出；
- 原始正文和完整轨迹保存在本地，默认只向模型返回最小证据片段。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

可选：执行一次受限的真实网络冒烟测试（会访问外部网站）：

```powershell
.\.venv\Scripts\python.exe scripts\smoke_research.py "Python 官方网站是什么"
```

## 项目结构

```text
cn-web-search-mcp/
├── src/cn_web_search_mcp/  # MCP 服务、任务编排、搜索与抓取实现
│   ├── core/sources/adapters/ # 来源 Adapter 协议、注册表、工厂与目录适配器
│   └── data/               # YAML 来源目录、路由策略和迁移期 Markdown
├── tests/                  # 单元测试与协议测试
├── references/             # 部署说明和架构边界
├── schemas/                # 数据结构定义
├── scripts/                # 安装与验证脚本
├── agents/                 # Agent 配置
├── SKILL.md                # 宿主 Agent 的精简调用规范
└── pyproject.toml          # Python 包配置
```

## 当前边界

- 直连搜索适配器依赖第三方页面结构，上游改版或反爬策略变化可能导致暂时失效。
- 无代理且未部署 SearXNG 时，可访问来源和稳定性取决于本机网络环境。
- 服务返回适合引用的结构化证据包；最终自然语言答案由调用它的 Agent 或模型生成。
- 进程重启后，遗留的 `queued` / `running` 任务会标记为中断，不会自动续跑。
- 自动质量判断能减少明显缺口，但不能替代对高风险结论的人工核验。
- YAML 中登记的来源不等于已实现；以 `cnws://sources/coverage` 为准。

更详细的设计不变量和数据边界见 [`references/architecture.md`](references/architecture.md)。

## License

本仓库暂未指定开源许可证。在添加明确的 `LICENSE` 文件前，默认保留全部权利。
