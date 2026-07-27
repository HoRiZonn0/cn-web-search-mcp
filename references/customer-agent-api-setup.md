# 从零获取 API Key 并接入 Agent

本文介绍如何从零部署一个客户独立的 CN Web Search API 实例、生成专属 API Key，并将搜索能力配置到其他 Agent。

示例环境：

- Windows PowerShell；
- 项目目录：`E:\work1_cn-web-search-skill\cn-web-search-mcp`；
- API 与 Agent 运行在同一台电脑；
- API 端口：`9001`；
- 客户 ID：`my-agent`。

API Key 不是从第三方平台申请的，而是由服务提供方使用项目内置的 `cn-web-search-provision` 命令生成。

## 1. 准备 Python 环境

进入项目：

```powershell
cd E:\work1_cn-web-search-skill\cn-web-search-mcp
```

创建虚拟环境：

```powershell
python -m venv .venv
```

安装项目：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

检查版本：

```powershell
.\.venv\Scripts\python.exe -c "import cn_web_search_mcp; print(cn_web_search_mcp.__version__)"
```

商业 MVP 版本应为：

```text
0.4.0
```

## 2. 准备 Docker

安装并启动 Docker Desktop。

检查 Docker Engine：

```powershell
docker info
```

如果出现以下错误：

```text
failed to connect to the docker API
dockerDesktopLinuxEngine
```

说明 Docker Desktop 或 Linux Container Engine 尚未启动。启动 Docker Desktop，等待状态变为 Running 后重试。

## 3. 构建 API 镜像

在项目根目录执行：

```powershell
docker build -t cn-web-search-mcp:0.4.0 .
```

查看镜像：

```powershell
docker images cn-web-search-mcp
```

应该能看到：

```text
REPOSITORY          TAG
cn-web-search-mcp   0.4.0
```

## 4. 生成客户实例和 API Key

执行：

```powershell
.\.venv\Scripts\cn-web-search-provision.exe `
  --customer-id my-agent `
  --output-dir deployments/my-agent `
  --plan starter `
  --monthly-credit-quota 1000 `
  --rate-limit-per-minute 5 `
  --max-active-jobs 2 `
  --public-port 9001 `
  --api-base-url http://127.0.0.1:9001
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--customer-id` | 客户或 Agent 的唯一标识，只能使用小写字母、数字、`_`、`-` |
| `--output-dir` | 客户独立配置和数据目录 |
| `--plan` | 套餐名称 |
| `--monthly-credit-quota` | 每月搜索积分 |
| `--rate-limit-per-minute` | 每分钟最多创建的搜索任务数 |
| `--max-active-jobs` | 最大排队和运行中任务数 |
| `--public-port` | 宿主机 API 端口 |
| `--api-base-url` | 交付给 Agent 的 API 地址 |

命令会输出类似：

```json
{
  "customer_id": "my-agent",
  "output_dir": "E:\\work1_cn-web-search-skill\\cn-web-search-mcp\\deployments\\my-agent",
  "api_base_url": "http://127.0.0.1:9001",
  "api_key": "sk_cnws_live_xxxxxxxxxxxxxxxxx",
  "api_key_prefix": "sk_cnws_live_xxxxx"
}
```

其中完整的：

```text
sk_cnws_live_xxxxxxxxxxxxxxxxx
```

就是客户专属 API Key。

生成目录结构：

```text
deployments/my-agent/
├── customer.env
├── customer.json
├── compose.yaml
├── OPERATIONS.txt
└── data/
```

文件用途：

| 文件 | 用途 |
|---|---|
| `customer.env` | 保存完整 API Key、套餐和容器配置，必须保密 |
| `customer.json` | 不包含完整 Key 的客户交付清单 |
| `compose.yaml` | 客户专属 Docker Compose 配置 |
| `OPERATIONS.txt` | 启停、状态和日志命令 |
| `data/` | 客户独立的 SQLite、缓存和证据目录 |

生成器默认拒绝覆盖已有客户目录，防止误删现有 API Key 和数据。

## 5. 重新读取 API Key

完整 Key 保存在：

```text
deployments/my-agent/customer.env
```

PowerShell 读取方式：

```powershell
$config = Get-Content deployments/my-agent/customer.env |
  ConvertFrom-StringData

$apiKey = $config.CNWS_API_BEARER_TOKEN
$apiKey
```

安全要求：

- 不要把 `customer.env` 提交到 Git；
- 不要把 Key 写进 Agent 的系统提示词；
- 不要把 Key 放在浏览器前端；
- 不要通过公开群聊或普通邮件发送；
- Agent 应通过环境变量或密钥管理系统读取 Key。

## 6. 启动客户 API 实例

进入客户目录：

```powershell
cd deployments/my-agent
```

启动：

```powershell
docker compose --env-file customer.env up -d
```

查看容器状态：

```powershell
docker compose --env-file customer.env ps
```

查看日志：

```powershell
docker compose --env-file customer.env logs -f
```

停止：

```powershell
docker compose --env-file customer.env down
```

重新启动：

```powershell
docker compose --env-file customer.env restart
```

返回项目根目录：

```powershell
cd E:\work1_cn-web-search-skill\cn-web-search-mcp
```

## 7. 验证 API

### 7.1 健康检查

健康检查不需要 API Key：

```powershell
Invoke-RestMethod http://127.0.0.1:9001/healthz
```

正常返回：

```json
{
  "status": "ok"
}
```

### 7.2 API 文档

Swagger UI：

```text
http://127.0.0.1:9001/docs
```

OpenAPI：

```text
http://127.0.0.1:9001/openapi.json
```

### 7.3 验证 Key 和额度

```powershell
$config = Get-Content deployments/my-agent/customer.env |
  ConvertFrom-StringData

$headers = @{
  Authorization = "Bearer $($config.CNWS_API_BEARER_TOKEN)"
}

Invoke-RestMethod `
  -Uri "http://127.0.0.1:9001/v1/account/usage" `
  -Headers $headers
```

返回内容包括：

- `customer_id`；
- `plan`；
- `monthly_credit_quota`；
- `credits_used`；
- `credits_remaining`；
- `rate_limit_per_minute`；
- `max_active_jobs`；
- `active_jobs`。

## 8. 手动执行一次搜索

### 8.1 创建任务

```powershell
$config = Get-Content deployments/my-agent/customer.env |
  ConvertFrom-StringData

$headers = @{
  Authorization = "Bearer $($config.CNWS_API_BEARER_TOKEN)"
  "Content-Type" = "application/json"
}

$body = @{
  question = "帮我查询最新的世界杯赛程"
  requirements = @(
    "给出剩余赛程"
    "转换为北京时间"
    "优先使用权威来源"
  )
  profile = "balanced"
  max_rounds = 3
  timezone = "Asia/Shanghai"
} | ConvertTo-Json

$job = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:9001/v1/research" `
  -Headers $headers `
  -Body $body

$job
```

返回示例：

```json
{
  "job_id": "rs_xxxxxxxxx",
  "status": "queued",
  "billing": {
    "customer_id": "my-agent",
    "plan": "starter",
    "credits_charged": 2,
    "credits_used": 2,
    "credits_remaining": 998
  }
}
```

积分规则：

| Profile | 积分 |
|---|---:|
| `fast` | 1 |
| `balanced` | 2 |
| `thorough` | 4 |

积分在任务被接受时扣除。状态轮询、结果读取和取消不扣积分。

### 8.2 查询状态

```powershell
$status = Invoke-RestMethod `
  -Uri "http://127.0.0.1:9001/v1/research/$($job.job_id)" `
  -Headers $headers

$status
```

终态包括：

```text
completed
unresolvable
failed
cancelled
```

### 8.3 获取结果

```powershell
$result = Invoke-RestMethod `
  -Uri "http://127.0.0.1:9001/v1/research/$($job.job_id)/result" `
  -Headers $headers

$result
```

任务尚未完成时，结果接口返回 HTTP 202；完成后返回 HTTP 200。

Agent 主要使用：

```text
result.answer_context.facts
result.answer_context.conflicts
result.answer_context.unresolved
result.quality
```

## 9. 使用 OpenAPI 配置 Agent

如果 Agent 平台支持导入 OpenAPI：

1. 导入：

   ```text
   http://127.0.0.1:9001/openapi.json
   ```

2. 认证类型选择：

   ```text
   HTTP Bearer
   ```

3. Bearer Token 填写：

   ```text
   sk_cnws_live_xxxxxxxxx
   ```

4. API Base URL 填写：

   ```text
   http://127.0.0.1:9001
   ```

如果平台要求手动填写请求头：

```http
Authorization: Bearer sk_cnws_live_xxxxxxxxx
```

`Bearer` 与 Key 之间必须有一个空格。

## 10. Agent 不支持 OpenAPI 时

可以添加一个 Python 工具，让工具内部完成创建任务、静默轮询和读取结果。

安装依赖：

```powershell
pip install requests
```

配置 Agent 运行环境：

```powershell
$env:CNWS_API_URL = "http://127.0.0.1:9001"
$env:CNWS_API_KEY = "sk_cnws_live_xxxxxxxxx"
```

Python 工具：

```python
import os
import time

import requests


API_URL = os.environ["CNWS_API_URL"].rstrip("/")
API_KEY = os.environ["CNWS_API_KEY"]

TERMINAL_STATUSES = {
    "completed",
    "unresolvable",
    "failed",
    "cancelled",
}


def cn_web_search(
    question: str,
    requirements: list[str] | None = None,
    profile: str = "balanced",
    max_rounds: int = 3,
    timeout_seconds: int = 600,
) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        f"{API_URL}/v1/research",
        headers=headers,
        json={
            "question": question,
            "requirements": requirements or [],
            "profile": profile,
            "max_rounds": max_rounds,
            "timezone": "Asia/Shanghai",
        },
        timeout=30,
    )
    response.raise_for_status()

    job_id = response.json()["job_id"]
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        status_response = requests.get(
            f"{API_URL}/v1/research/{job_id}",
            headers=headers,
            timeout=30,
        )
        status_response.raise_for_status()
        job_status = status_response.json()["status"]

        if job_status in TERMINAL_STATUSES:
            result_response = requests.get(
                f"{API_URL}/v1/research/{job_id}/result",
                headers=headers,
                timeout=30,
            )
            result_response.raise_for_status()
            return result_response.json()

        time.sleep(2)

    raise TimeoutError(
        f"搜索任务 {job_id} 在 {timeout_seconds} 秒内没有完成"
    )
```

工具定义示例：

```json
{
  "name": "cn_web_search",
  "description": "搜索中文互联网，执行多来源检索、正文抓取和质量评估，返回带URL的证据结果。",
  "parameters": {
    "type": "object",
    "properties": {
      "question": {
        "type": "string",
        "description": "需要搜索和回答的问题"
      },
      "requirements": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "description": "答案必须覆盖的具体要求"
      },
      "profile": {
        "type": "string",
        "enum": ["fast", "balanced", "thorough"],
        "default": "balanced"
      },
      "max_rounds": {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "default": 3
      }
    },
    "required": ["question"]
  }
}
```

## 11. Agent 提示词

建议加入 Agent 的系统提示词或工具说明：

```text
当用户的问题需要互联网搜索、最新信息、权威来源核验或多来源交叉验证时，调用 cn_web_search。

调用规则：
1. question 使用用户完整的原始问题。
2. 将用户明确要求拆分到 requirements。
3. 一般任务使用 balanced；高风险或深入核验使用 thorough。
4. 搜索和状态轮询必须静默，不向用户输出中间进度。
5. 工具返回后，只根据 result.answer_context.facts 中带 URL 的事实回答。
6. 每个重要事实都应附带对应来源 URL。
7. 必须披露 conflicts 和 unresolved。
8. 如果状态为 unresolvable 或 failed，不得根据模型自身知识猜测补全。
```

## 12. API 和 Agent 的网络地址

### 同一台电脑

```text
http://127.0.0.1:9001
```

### Agent 运行在另一个 Docker 容器

Windows/macOS Docker Desktop 通常可以使用：

```text
http://host.docker.internal:9001
```

如果两个容器位于同一个 Compose 网络，推荐使用 API 服务名和容器端口。

### Agent 位于另一台服务器

应配置 HTTPS 域名，例如：

```text
https://search.example.com
```

使用 Caddy、Nginx 或云网关把域名反向代理到本机 API 端口。不要把未加密的 API 端口直接暴露到公网。

生成客户时填写：

```powershell
--api-base-url https://search.example.com
```

## 13. 常见错误

### 401 Unauthorized

原因：

- 缺少 `Authorization`；
- Key 错误；
- `Bearer` 拼写错误；
- `Bearer` 与 Key 之间没有空格；
- Key 已轮换。

正确格式：

```http
Authorization: Bearer sk_cnws_live_xxxxxxxxx
```

### 404 Not Found

通常表示 `job_id` 不存在，或者请求发送到了错误的 API 实例。

### 422 Unprocessable Entity

请求参数不符合要求，例如：

- `question` 为空；
- `profile` 不是 `fast`、`balanced`、`thorough`；
- `max_rounds` 不在 1 到 5；
- requirements 超过限制。

### 429 Too Many Requests

响应中的错误代码可能是：

```text
monthly_quota_exceeded
rate_limit_exceeded
concurrency_limit_exceeded
```

分别表示：

- 月度积分已用完；
- 每分钟创建任务过多；
- 当前排队和运行中的任务达到上限。

短期限流响应可能包含：

```http
Retry-After: 2
```

Agent 应等待后重试，不要高频循环请求。

### API 无法访问

检查：

```powershell
docker compose --env-file customer.env ps
docker compose --env-file customer.env logs
```

然后检查：

```powershell
Invoke-RestMethod http://127.0.0.1:9001/healthz
```

还需要确认端口没有被其他程序占用。

## 14. Key 轮换

生成新的高熵 Key，替换：

```text
deployments/my-agent/customer.env
```

中的：

```text
CNWS_API_BEARER_TOKEN=...
```

然后重建容器：

```powershell
cd deployments/my-agent
docker compose --env-file customer.env up -d --force-recreate
```

将新 Key 安全发送给 Agent 使用方。容器重建后旧 Key 立即失效。

当前商业 MVP 一个实例只支持一个有效 Key，不支持新旧 Key 同时生效的平滑轮换。

## 15. 数据备份

客户数据位于：

```text
deployments/my-agent/data/
```

建议先停止容器：

```powershell
cd deployments/my-agent
docker compose --env-file customer.env down
```

复制整个 `data/` 目录后重新启动：

```powershell
docker compose --env-file customer.env up -d
```

备份内容包括：

- 任务状态；
- 月度积分记录；
- 搜索缓存；
- 域名健康状态；
- 搜索证据和任务产物。

## 16. 客户最终需要获得的内容

服务提供方向客户交付：

```text
API 地址
专属 API Key
Swagger 地址
OpenAPI 地址
套餐名称
月度积分
每分钟任务限制
最大并发任务数
数据保留和支持政策
Key 泄露后的轮换流程
```

客户侧只需要：

1. 将 API Key 保存到环境变量或密钥管理系统；
2. 导入 OpenAPI 或注册 `cn_web_search` 工具；
3. 使用 Bearer Token 调用 API；
4. 静默轮询任务；
5. 根据最终证据生成回答。
