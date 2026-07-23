# 来源目录维护

## 数据边界

- `sources.yaml`：运行时静态来源能力、入口、证据资格、限流和 Adapter 引用。
- `routing.yaml`：查询意图到主源、备源和核验源的选择策略。
- `authoritative-sites.md`：迁移期人工对照，不再是线上运行时数据源。
- SQLite：成功率、耗时、限流、阻断和缓存等动态状态。

## 核心规则

1. 来源出现在 YAML 中不代表已实现；以运行覆盖报告为准。
2. `discovery_only: true` 的端点必须同时设置 `evidence_eligible: false`。
3. 主页和搜索结果页只用于发现具体内容，不得直接成为事实证据。
4. API Key 只写环境变量名 `key_env`，不得把密钥写入目录。
5. 新增 fallback 时必须引用已存在且不同于自身的来源 ID。
6. 四个必需搜索渠道始终执行；意图定向来源只能补充结果。
7. 每个 Adapter 必须通过 `SourceAdapterRegistry` 绑定已有来源和端点；不得手写与 YAML 脱节的覆盖清单。
8. `discovery_only` Adapter 可以执行域名定向搜索，但不得计入来源自身直接 API 的 `executable` 覆盖。

## 迁移期生成与检查

重新从旧 Markdown 生成完整目录：

```powershell
.\.venv\Scripts\python.exe scripts\migrate_authorities_to_yaml.py
```

该命令会覆盖 `sources.yaml`。迁移期新增的系统来源也必须同步维护在迁移脚本中，直至旧 Markdown 正式退役。

运行来源目录与 Adapter 校验：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_source_registry.py tests/test_source_routing.py tests/test_source_adapters.py -q
```

查看 MCP 诊断：

```text
cnws://sources/catalog
cnws://sources/coverage
cnws://sources/route/{query}
```
