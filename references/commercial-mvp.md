# 每客户独立实例商业 MVP

该模式面向早期付费客户：一个客户对应一个 API 进程或容器、一个 Bearer API Key、一个数据目录和一组套餐限制。实例之间不共享任务、缓存、证据或额度。

## 架构边界

```text
客户 Agent
  → HTTPS / 反向代理
    → 客户专属容器
      → 专属 API Key
      → 专属 SQLite 与 artifacts
      → 专属额度、限流和并发
```

它不是共享数据库的多租户平台。客户数量较少时，这种方式有更清晰的故障和数据隔离边界。

## 构建镜像

在仓库根目录执行：

```powershell
docker build -t cn-web-search-mcp:0.4.0 .
```

正式发布时可以将镜像推到私有仓库，并在生成客户实例时指定：

```text
--image registry.example.com/cn-web-search-mcp:0.4.0
```

镜像使用非 root 用户运行，数据写入 `/data`，并通过 `/healthz` 执行健康检查。

## 创建客户

```powershell
.\.venv\Scripts\cn-web-search-provision.exe `
  --customer-id acme `
  --output-dir deployments/acme `
  --plan starter `
  --monthly-credit-quota 1000 `
  --rate-limit-per-minute 5 `
  --max-active-jobs 2 `
  --max-job-workers 2 `
  --public-port 9001 `
  --bind-address 127.0.0.1 `
  --api-base-url https://search-acme.example.com
```

生成器会：

1. 校验客户 ID 和套餐限制；
2. 生成 `sk_cnws_live_` 开头的随机 Key；
3. 创建客户专属 Compose 配置和数据目录；
4. 生成不包含完整 Key 的 `customer.json`；
5. 如果目标目录已有文件则拒绝覆盖。

完整 Key 会打印到终端，同时保存在 `customer.env` 供容器注入。该文件必须进入服务器密钥备份范围，但不得提交 Git、发送到群聊或写进客户侧代码。

## 启动和验证

```powershell
cd deployments/acme
docker compose --env-file customer.env up -d
docker compose --env-file customer.env ps
docker compose --env-file customer.env logs -f
```

本机检查：

```powershell
Invoke-RestMethod http://127.0.0.1:9001/healthz
```

检查客户额度：

```powershell
$envData = Get-Content customer.env | ConvertFrom-StringData
$headers = @{ Authorization = "Bearer $($envData.CNWS_API_BEARER_TOKEN)" }
Invoke-RestMethod `
  -Uri "http://127.0.0.1:9001/v1/account/usage" `
  -Headers $headers
```

## 套餐和扣费

任务被 API 接受时原子预扣积分：

| Profile | 积分 |
|---|---:|
| `fast` | 1 |
| `balanced` | 2 |
| `thorough` | 4 |

查询状态、读取结果、读取用量和取消任务不扣费。当前 MVP 按“已接受任务”计费，因此任务稍后搜索失败或客户主动取消不会自动退积分；如果商业条款需要失败退款，应在后续版本增加结算状态。

月度周期按 UTC 自然月计算。积分事件持久化在客户自己的 SQLite 中，重启不会清零。

限制触发时返回 HTTP 429：

```json
{
  "detail": {
    "code": "monthly_quota_exceeded",
    "message": "monthly research credit quota exceeded"
  }
}
```

可能的代码：

- `monthly_quota_exceeded`
- `rate_limit_exceeded`
- `concurrency_limit_exceeded`

短期限流和并发响应还会携带 `Retry-After`。

## 客户交付

向客户提供：

- HTTPS API 地址；
- 专属 API Key；
- `/docs`；
- `/openapi.json`；
- 套餐额度、速率和并发；
- 数据保留和服务支持政策；
- Key 泄露后的联系和轮换流程。

客户只需要把 Key 放入服务端环境变量或密钥管理系统，并使用：

```http
Authorization: Bearer sk_cnws_live_xxx
```

浏览器前端不应直接持有该 Key。

## HTTPS

Compose 默认只绑定 `127.0.0.1`。使用 Caddy、Nginx 或云网关把客户域名反向代理到对应本机端口并启用 HTTPS。不要把容器端口直接暴露到公网。

不同客户必须使用不同域名或路由、端口、Compose project name、Key 和数据目录。

## Key 轮换

当前 MVP 的轮换方式：

1. 生成新的高熵随机 Key；
2. 更新客户目录的 `customer.env` 中 `CNWS_API_BEARER_TOKEN`；
3. 执行：

```powershell
docker compose --env-file customer.env up -d --force-recreate
```

4. 通知客户切换；
5. 旧 Key 随容器重建立即失效。

该模式暂不支持新旧 Key 并存的平滑窗口；需要零停机轮换时应在 API 网关层维护双 Key。

## 备份与恢复

备份整个客户 `data/`：

- `jobs.sqlite3`
- SQLite WAL/SHM 文件（运行中备份时必须使用 SQLite 在线备份或先停止容器）
- `artifacts/`

最稳妥的 MVP 流程是先停止客户容器，复制 `data/`，然后重新启动。恢复时使用相同客户配置挂载备份目录。

## 当前限制

- 一个实例只有一个客户和一个有效 API Key；
- 使用 SQLite 和进程内任务线程池；
- 每分钟限流状态在进程内，重启后清空；
- 已接受任务按 profile 固定积分计费，不按真实搜索源调用量结算；
- 不提供支付、发票、客户后台或自动续费；
- 不支持多节点共享任务队列。

当客户数量和并发增长后，应升级为数据库 API Key、`customer_id` 行级授权、PostgreSQL、Redis 限流与任务队列、幂等创建、用量账单和 Webhook。
