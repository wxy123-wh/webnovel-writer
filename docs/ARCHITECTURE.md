# Webnovel Writer 架构文档 - M1/M2/M3 阶段

## 概述

Webnovel Writer 是面向 Agent 的长篇网文创作系统。当前仓库已经形成清晰方向，并已在选定的商业化模型下完成主线落地：

当前主线支持的商业化形态为：**GPL v3 自托管单租户部署 + 有偿支持 / 实施服务**。当前架构并不把公网多租户托管 SaaS 作为主线承诺。

- **M1 阶段**：删除写接口，Dashboard 改为纯展示（已完成）
- **M2 阶段**：建立统一 CLI 入口 `webnovel codex`，提供索引产物与状态查询（已落地）
- **M3 阶段**：会话级 Skill 加载，提供 `rag verify` 命令入口与 benchmark 契约（已落地）
- **当前主线**：以 `webnovel agent` 作为直接内嵌 LLM API 的写作入口，保留既有 pipeline / index / RAG 数据面

## 架构分层

### 第一层：Agent / CLI 统一入口（`webnovel agent`）

所有主写作操作由内嵌 LLM API 的 agent 承载，CLI 负责提供稳定入口与运行时编排。

```bash
# 执行整章 agent pipeline
webnovel agent run --chapter <n> --profile <battle|description|consistency> --publish --project-root <path>

# 可选的 agent 会话管理
webnovel agent session start --profile <battle|description|consistency> --project-root <path>
webnovel agent session stop --session-id <id> --project-root <path>

# 索引管理
webnovel codex index status --project-root <path>

# RAG 验证
webnovel codex rag verify --project-root <path> --report json
```

**实现文件**：
- `scripts/data_modules/agent_cli.py` - Agent 命令入口
- `scripts/data_modules/codex_cli.py` - CLI 命令入口
- `scripts/data_modules/generation_client.py` - OpenAI-compatible 生成型 LLM API 客户端
- `scripts/data_modules/session_manager.py` - 会话管理
- `scripts/data_modules/incremental_indexer.py` - 增量索引
- `scripts/data_modules/rag_verifier.py` - RAG 验证
- `scripts/pipeline/generators.py` - 基于内嵌 LLM API 的阶段生成

### 第二层：Dashboard（纯展示）

Dashboard 前端改为只读展示，当前主线运行时仅挂载只读路由。

**已删除的写接口**（19 个端点）：
- `POST /api/skills` - 创建 Skill
- `PATCH /api/skills/{id}` - 更新 Skill
- `POST /api/skills/{id}/enable` - 启用 Skill
- `POST /api/skills/{id}/disable` - 禁用 Skill
- `DELETE /api/skills/{id}` - 删除 Skill
- `POST /api/settings/files/write` - 写入设定文件
- `POST /api/settings/dictionary/extract` - 抽离词典
- `POST /api/settings/dictionary/conflicts/{id}/resolve` - 解决冲突
- `POST /api/outlines/split/preview` - 预览拆分
- `POST /api/outlines/split/apply` - 应用拆分
- `POST /api/outlines/resplit/preview` - 预览重拆
- `POST /api/outlines/resplit/apply` - 应用重拆
- `POST /api/outlines/order/validate` - 验证顺序
- `POST /api/edit-assist/preview` - 预览编辑建议
- `POST /api/edit-assist/apply` - 应用编辑建议
- `GET /api/edit-assist/logs` - 获取编辑日志
- `POST /api/codex/split-dialog/open` - 打开拆分对话
- `POST /api/codex/file-edit/open` - 打开文件编辑
- `POST /api/runtime/migrate` - 运行时迁移

**保留的只读接口**：
- `GET /api/project/root` - 项目根目录
- `GET /api/project/info` - 项目信息
- `GET /api/entities` - 实体列表
- `GET /api/relationships` - 关系列表
- `GET /api/chapters` - 章节列表
- `GET /api/scenes` - 场景列表
- `GET /api/reading-power` - 阅读力
- `GET /api/review-metrics` - 评审指标
- `GET /api/files/tree` - 文件树
- `GET /api/files/read` - 读取文件
- `GET /api/events` - SSE 实时推送

**改造的前端页面**（4 个页面改为只读）：
- `SkillsPage` - 技能管理（只读）
- `SettingsPage` - 设定集（只读）
- `OutlineWorkspacePage` - 双纲工作台（只读）
- `FilesPage` - 文档浏览（只读）

### 第三层：会话级 Skill 加载

Skill 只在当前写作会话加载，会话结束自动清理。

**目录结构**：
```
webnovel-writer/scripts/codex_skill_profiles/
├── battle/
│   └── README.md
├── description/
│   └── README.md
└── consistency/
    └── README.md

.webnovel/codex/sessions/
├── session-abc123/
│   ├── metadata.json
│   └── skills/
│       ├── battle/
│       ├── description/
│       └── consistency/
└── session-def456/
    ├── metadata.json
    └── skills/
        └── ...
```

### 第四层：RAG 验证

当前代码中，`rag verify` 已具备统一命令入口、连通性检查与 benchmark 契约读取能力。仓库内 CI 负责验证门禁链路本身；实际商业交付时，正确性 / 性能应以目标项目自己的 benchmark 报告作为验收依据。

目标中的 RAG 验证分三层：

1. **连通性**
   - `vectors.db` 可打开
   - `index.db` 可打开
   - `rag_schema_meta` 存在且版本合法
   - 最小检索调用可执行

2. **正确性**
   - Hit@5 >= 0.90
   - MRR@10 >= 0.70
   - 章节约束正确率 >= 0.98

3. **性能**
   - 检索延迟 p95 <= 700ms
   - 检索延迟 p99 <= 1200ms
   - 单文件增量索引 p95 <= 1500ms
   - 文件变更到可检索可见时间 p95 <= 3s

## 数据流

### 写作流程

```
Codex 桌面端
    ↓
webnovel codex session start --profile battle
    ↓
SessionManager 创建会话
    ↓
加载 battle profile Skill
    ↓
Codex 直接编辑文件
    ↓
IncrementalIndexer 生成 / 更新索引产物
    ↓
更新 fast-index.json（章节号/场景标签倒排）
    ↓
webnovel codex index status 查询索引状态
    ↓
webnovel codex session stop --session-id xxx
    ↓
SessionManager 清理会话 Skill
```

### 查询流程

```
Dashboard 前端
    ↓
GET /api/entities（只读查询）
    ↓
FastAPI 后端
    ↓
SQLite index.db（只读访问）
    ↓
返回 JSON 响应
```

## 文件组织

```
webnovel-writer/
├── dashboard/
│   ├── routers/
│   │   ├── __init__.py (仅保留只读路由)
│   │   └── runtime.py (仅保留只读接口)
│   ├── services/
│   │   └── runtime/ (仅保留只读服务)
│   ├── models/
│   │   ├── common.py (保留)
│   │   └── runtime.py (仅保留只读模型)
│   ├── app.py (仅挂载只读路由)
│   └── frontend/ (改造为只读展示)
├── scripts/
│   ├── webnovel.py (主入口)
│   ├── data_modules/
│   │   ├── codex_cli.py (CLI 命令入口)
│   │   ├── session_manager.py (会话管理)
│   │   ├── incremental_indexer.py (增量索引)
│   │   ├── rag_verifier.py (RAG 验证)
│   │   └── ... (其他数据模块)
│   └── codex_skill_profiles/ (Skill 模板库)
│       ├── battle/
│       ├── description/
│       └── consistency/
└── docs/
    ├── prd-refined.md (需求冻结稿)
    ├── ARCHITECTURE.md (本文件)
    └── CLI_REFERENCE.md (CLI 参考)
```

## 验收标准

### M1 验收 ✓
- [x] 后端 19 个写端点全部删除
- [x] 对应 service 写逻辑全部删除
- [x] 前端 4 页面改为只读展示
- [x] 前端写 API 模块全部删除
- [x] 测试通过率 >= 95%

### M2 当前状态
- [x] `webnovel codex session start` 可执行
- [x] 扫描式索引生成与索引状态落盘可用（当前主线不再把文件监听自动触发作为商业承诺）
- [x] 章节号/场景标签快速定位可用
- [x] 索引状态持久化到 `.webnovel/codex/`

### M3 当前状态
- [x] 会话 Skill 不落全局路径
- [x] `rag verify` 已按 benchmark 契约执行门禁；商业交付以目标项目自己的 benchmark 报告作为验收依据
- [x] CI 集成生效（`app-release-gate.yml` 会执行 `rag verify` 发布门禁）

## 迁移指南

### 对于历史脚本

如果你的脚本曾调用已删除的写接口（如 `POST /api/skills`），需要迁移到 CLI：

**旧方式**（已删除）：
```bash
curl -X POST http://localhost:8765/api/skills \
  -H "Content-Type: application/json" \
  -d '{"name": "my-skill", "enabled": true}'
```

**新方式**（使用 CLI）：
```bash
webnovel codex session start --profile battle --project-root /path/to/project
```

### 对于 Codex 集成

Codex 应直接调用 CLI 命令，而不是 HTTP API：

```python
import subprocess
import json

# 启动会话
result = subprocess.run([
    "python", "-m", "webnovel.py", "codex", "session", "start",
    "--profile", "battle",
    "--project-root", "/path/to/project"
], capture_output=True, text=True)

session_info = json.loads(result.stdout)
session_id = session_info["session_id"]

# ... 进行写作 ...

# 停止会话
subprocess.run([
    "python", "-m", "webnovel.py", "codex", "session", "stop",
    "--session-id", session_id
])
```

## 性能指标

- 会话启动时间：< 500ms
- 增量索引（单文件 <= 10k 字）：p95 <= 1500ms
- 文件变更到可检索可见：p95 <= 3s
- 快速定位查询：< 50ms

## 安全性

- Dashboard 已支持最小内置 Basic Auth，适合单租户 / 受信任环境；如需更强公网部署策略，仍可在反向代理层叠加认证
- CLI 命令在本地执行，无网络暴露
- 会话 Skill 隔离在 `.webnovel/codex/sessions/` 目录，不污染全局
- 所有文件操作经过 path_guard 防穿越校验

## 后续扩展

1. **文件监听优化**：当前使用轮询，可升级为 OS 原生文件监听（watchdog）
2. **RAG 性能优化**：可添加缓存层、向量数据库优化
3. **Skill 市场**：可建立 Skill 模板市场，支持在线下载
4. **多用户支持**：当前为单用户，可扩展为多用户工作区
