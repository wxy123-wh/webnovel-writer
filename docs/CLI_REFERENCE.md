# Webnovel Writer CLI 参考手册

## 概述

`webnovel codex` 是 Codex 桌面端与 Webnovel Writer 系统的统一接口。所有写作相关的操作都通过 CLI 命令执行。

## 快速开始

### 1. 启动写作会话

```bash
webnovel codex session start --profile battle --project-root /path/to/project
```

**输出示例**：
```json
{
  "status": "ok",
  "session_id": "session-abc123def456",
  "profile": "battle",
  "project_root": "/path/to/project",
  "message": "会话已启动: session-abc123def456（profile: battle）"
}
```

**参数说明**：
- `--profile` (必需)：Skill profile，可选值：`battle`、`description`、`consistency`
- `--project-root` (可选)：项目根目录，如不指定则自动查找

### 2. 停止写作会话

```bash
webnovel codex session stop --session-id session-abc123def456
```

**输出示例**：
```json
{
  "status": "ok",
  "session_id": "session-abc123def456",
  "message": "会话已停止: session-abc123def456"
}
```

**参数说明**：
- `--session-id` (必需)：会话 ID，由 `session start` 返回

### 3. 查询索引状态

```bash
webnovel codex index status --project-root /path/to/project
```

**输出示例**：
```json
{
  "status": "ok",
  "project_root": "/path/to/project",
  "index": {
    "indexed": true,
    "last_updated": "2026-03-28T10:30:45.123456",
    "chapter_count": 150,
    "scene_count": 1250,
    "file_count": 45
  }
}
```

**参数说明**：
- `--project-root` (可选)：项目根目录，如不指定则自动查找

### 4. 验证 RAG 当前状态

```bash
webnovel codex rag verify --project-root /path/to/project --report json
```

**输出示例**（用于说明返回结构。正确性 / 性能字段必须来自项目自己的 benchmark 产物；仓库内 CI 只验证门禁链路本身，不能直接替代客户项目验收）：
```json
{
  "status": "ok",
  "passed": true,
  "timestamp": "2026-03-28T10:30:45.123456",
  "connectivity": {
    "status": "ok",
    "checks": {
      "vectors_db_exists": true,
      "index_db_exists": true,
      "vectors_db_readable": true,
      "index_db_readable": true,
      "rag_schema_meta_exists": true,
      "schema_version_present": true
    },
    "schema_meta_source": "vectors.db",
    "errors": []
  },
  "correctness": {
    "status": "ok",
    "metrics": {
      "hit_at_5": 0.95,
      "mrr_at_10": 0.80,
      "chapter_constraint_accuracy": 0.99
    },
    "thresholds": {
      "hit_at_5": 0.90,
      "mrr_at_10": 0.70,
      "chapter_constraint_accuracy": 0.98
    },
    "passed": true,
    "source": {
      "path": "/path/to/project/.webnovel/codex/rag-benchmark.json",
      "exists": true
    },
    "errors": []
  },
  "performance": {
    "status": "ok",
    "metrics": {
      "p95_latency_ms": 650,
      "p99_latency_ms": 1000,
      "incremental_index_p95_ms": 1400,
      "file_change_to_searchable_p95_ms": 2500
    },
    "thresholds": {
      "p95_latency_ms": 700,
      "p99_latency_ms": 1200,
      "incremental_index_p95_ms": 1500,
      "file_change_to_searchable_p95_ms": 3000
    },
    "passed": true,
    "source": {
      "path": "/path/to/project/.webnovel/codex/rag-benchmark.json",
      "exists": true
    },
    "errors": []
  }
}
```

**参数说明**：
- `--project-root` (可选)：项目根目录，如不指定则自动查找
- `--report` (可选)：报告格式，可选值：`json`（默认）、`text`

## 完整命令参考

### webnovel codex session start

启动新的写作会话并加载指定 profile 的 Skill。

```bash
webnovel codex session start \
  --profile <battle|description|consistency> \
  [--project-root <path>]
```

**返回值**：
- 成功：返回 JSON，包含 `session_id`，exit code 0
- 失败：返回错误 JSON，exit code 1

**Skill Profile 说明**：
- `battle`：战斗场景相关 Skill
- `description`：描写场景相关 Skill
- `consistency`：一致性检查相关 Skill

### webnovel codex session stop

停止会话并清理会话级 Skill。

```bash
webnovel codex session stop --session-id <id>
```

**返回值**：
- 成功：返回 JSON，exit code 0
- 失败：返回错误 JSON，exit code 1

### webnovel codex index status

查询项目的索引状态。

```bash
webnovel codex index status [--project-root <path>]
```

**返回值**：
- 成功：返回 JSON，包含索引统计信息，exit code 0
- 失败：返回错误 JSON，exit code 1

### webnovel codex rag verify

验证 RAG 系统当前状态。当前连通性检查会直接执行；正确性 / 性能字段必须来自 `.webnovel/codex/rag-benchmark.json` 等真实 benchmark 产物。若 benchmark 文件缺失、损坏或缺少必需指标，命令会直接返回失败。

```bash
webnovel codex rag verify \
  [--project-root <path>] \
  [--report <json|text>]
```

**返回值**：
- 当前报告通过：返回 JSON，exit code 0
- 当前报告未通过：返回 JSON，exit code 1

## 错误处理

所有命令失败时返回结构化错误 JSON：

```json
{
  "status": "error",
  "error_code": "session_start_failed",
  "message": "具体错误信息"
}
```

**常见错误码**：
- `session_start_failed` - 会话启动失败
- `session_stop_failed` - 会话停止失败
- `index_status_failed` - 索引查询失败
- `rag_verify_failed` - RAG 验证失败

## 集成示例

### Python 集成

```python
import subprocess
import json

def start_session(profile, project_root):
    """启动写作会话。"""
    result = subprocess.run([
        "python", "-m", "webnovel.py", "codex", "session", "start",
        "--profile", profile,
        "--project-root", project_root
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"启动会话失败: {result.stderr}")
    
    return json.loads(result.stdout)

def stop_session(session_id):
    """停止写作会话。"""
    result = subprocess.run([
        "python", "-m", "webnovel.py", "codex", "session", "stop",
        "--session-id", session_id
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"停止会话失败: {result.stderr}")
    
    return json.loads(result.stdout)

def verify_rag(project_root):
    """验证 RAG 指标。"""
    result = subprocess.run([
        "python", "-m", "webnovel.py", "codex", "rag", "verify",
        "--project-root", project_root,
        "--report", "json"
    ], capture_output=True, text=True)
    
    report = json.loads(result.stdout)
    return report["passed"]

# 使用示例
try:
    session = start_session("battle", "/path/to/project")
    print(f"会话已启动: {session['session_id']}")
    
    # ... 进行写作 ...
    
    stop_session(session["session_id"])
    print("会话已停止")
except Exception as e:
    print(f"错误: {e}")
```

### Shell 集成

```bash
#!/bin/bash

# 启动会话
SESSION_JSON=$(python -m webnovel.py codex session start \
  --profile battle \
  --project-root /path/to/project)

SESSION_ID=$(echo "$SESSION_JSON" | jq -r '.session_id')
echo "会话已启动: $SESSION_ID"

# ... 进行写作 ...

# 停止会话
python -m webnovel.py codex session stop --session-id "$SESSION_ID"
echo "会话已停止"
```

## 性能指标

| 操作 | 预期耗时 |
|------|--------|
| 会话启动 | < 500ms |
| 会话停止 | < 100ms |
| 索引查询 | < 50ms |
| RAG 验证 | < 5s |

## 常见问题

### Q: 如何找到项目根目录？

A: 项目根目录是包含 `.webnovel/state.json` 的目录。如果不指定 `--project-root`，CLI 会自动从当前目录向上查找。

### Q: 会话 ID 有什么用？

A: 会话 ID 用于标识一个独立的写作会话。会话结束时必须使用相同的 ID 来停止会话并清理资源。

### Q: 可以同时启动多个会话吗？

A: 可以。每个会话都有独立的 ID 和 Skill 目录，互不影响。

### Q: Skill profile 可以自定义吗？

A: 当前支持三个预定义的 profile：`battle`、`description`、`consistency`。后续版本可能支持自定义 profile。

### Q: RAG 验证失败怎么办？

A: 先检查 `.webnovel/vectors.db` 和 `.webnovel/index.db` 是否存在且可读。如果问题持续，请重新运行索引，并注意当前正确性 / 性能指标仍需结合真实基准解释。

## 更新日志

### v0.1.0 (2026-03-28)

- 初始版本
- 实现 `session start/stop` 命令
- 实现 `index status` 命令
- 实现 `rag verify` 命令
