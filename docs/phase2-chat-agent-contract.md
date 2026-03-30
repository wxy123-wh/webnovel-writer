# Phase 2 Chat Agent — 契约冻结文档

> 日期：2026-03-31
> 状态：Phase 2 唯一实现基准

## 1. 产品形态

Webnovel Writer Phase 2 在现有 `dashboard/` FastAPI 应用上增加 Chat Agent 入口。
用户通过对话界面与写作 Agent 交互；Skill 库按会话装载；Pipeline/RAG 作为底层能力被 Agent 调用。

Phase 2 不新建 `apps/chat-ui/` 独立应用，而是在 `dashboard/` 上扩展，后续再考虑抽取。

## 2. API 端点契约

### 2.1 Chat 生命周期

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/chat/chats` | 列出当前项目的所有对话 |
| `POST` | `/api/chat/chats` | 创建新对话 |
| `GET` | `/api/chat/chats/{chat_id}` | 获取对话元信息 |
| `DELETE` | `/api/chat/chats/{chat_id}` | 删除对话 |

### 2.2 消息

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/chat/chats/{chat_id}/messages` | 获取对话消息历史 |
| `POST` | `/api/chat/chats/{chat_id}/messages` | 发送用户消息并触发 Agent 响应 |

### 2.3 流式响应

| 方法 | 路径 | 用途 |
|------|------|------|
| `POST` | `/api/chat/chats/{chat_id}/stream` | 发送消息并获取 SSE 流式响应 |

### 2.4 Skill 管理

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/chat/skills` | 列出可用 Skills |
| `GET` | `/api/chat/chats/{chat_id}/skills` | 获取对话已挂载的 Skills |
| `PATCH` | `/api/chat/chats/{chat_id}/skills` | 更新对话 Skill 挂载 |

## 3. 请求/响应 Schema

### 3.1 创建对话

```json
// POST /api/chat/chats
// Request:
{
  "title": "第1章写作",
  "profile": "xianxia",           // 可选，默认无 profile
  "skill_ids": ["webnovel-write"]  // 可选，初始挂载的 skills
}

// Response:
{
  "chat_id": "chat-a1b2c3d4e5f6",
  "title": "第1章写作",
  "profile": "xianxia",
  "created_at": "2026-03-31T10:00:00Z",
  "updated_at": "2026-03-31T10:00:00Z"
}
```

### 3.2 发送消息（非流式）

```json
// POST /api/chat/chats/{chat_id}/messages
// Request:
{
  "content": "帮我写第1章的开头",
  "role": "user"  // 固定为 "user"
}

// Response:
{
  "message_id": "msg-xxxx",
  "role": "assistant",
  "status": "complete",
  "parts": [
    {
      "part_id": "part-xxxx",
      "type": "text",
      "payload": { "content": "以下是第1章的开头..." }
    }
  ],
  "created_at": "2026-03-31T10:01:00Z"
}
```

### 3.3 发送消息（流式 SSE）

```json
// POST /api/chat/chats/{chat_id}/stream
// Request:
{
  "content": "帮我写第1章的开头"
}

// Response: text/event-stream
// 见第 4 节 SSE 事件协议
```

### 3.4 Skill 挂载

```json
// PATCH /api/chat/chats/{chat_id}/skills
// Request:
{
  "skills": [
    { "skill_id": "webnovel-write", "enabled": true },
    { "skill_id": "webnovel-review", "enabled": false }
  ]
}

// Response:
{
  "chat_id": "chat-a1b2c3d4e5f6",
  "skills": [
    {
      "skill_id": "webnovel-write",
      "name": "网文写作",
      "description": "核心写作能力",
      "enabled": true,
      "source": "system"
    }
  ]
}
```

## 4. SSE 事件协议

所有 SSE 事件格式：`event: <type>\ndata: <json>\n\n`

### 4.1 事件类型

| 事件 | 方向 | 用途 |
|------|------|------|
| `message_start` | server → client | Agent 开始响应，携带 message_id |
| `text_delta` | server → client | 文本增量 |
| `tool_call` | server → client | Agent 调用工具/skill |
| `tool_result` | server → client | 工具/skill 执行结果 |
| `message_complete` | server → client | Agent 响应完成 |
| `message_error` | server → client | 发生错误 |
| `heartbeat` | server → client | 保活，每 15 秒 |

### 4.2 事件载荷

```json
// message_start
{ "message_id": "msg-xxxx", "chat_id": "chat-xxxx" }

// text_delta
{ "delta": "以下是第1章的开头..." }

// tool_call
{
  "call_id": "call-xxxx",
  "skill_id": "webnovel-write",
  "name": "generate_plot",
  "arguments": { "chapter_num": 1 }
}

// tool_result
{
  "call_id": "call-xxxx",
  "status": "success",  // "success" | "error"
  "output": { "plot": "..." }
}

// message_complete
{ "message_id": "msg-xxxx", "usage": { "total_tokens": 1234 } }

// message_error
{ "message_id": "msg-xxxx", "error": "generation failed", "code": "provider_error" }

// heartbeat
{ "ts": "2026-03-31T10:00:00Z" }
```

## 5. 数据库 Schema

存储位置：`.webnovel/chat.db`（SQLite）

### 5.1 chats 表

```sql
CREATE TABLE IF NOT EXISTS chats (
    chat_id     TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    profile     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

### 5.2 messages 表

```sql
CREATE TABLE IF NOT EXISTS messages (
    message_id  TEXT PRIMARY KEY,
    chat_id     TEXT NOT NULL REFERENCES chats(chat_id),
    role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    status      TEXT NOT NULL DEFAULT 'complete' CHECK(status IN ('streaming', 'complete', 'error')),
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
```

### 5.3 message_parts 表

```sql
CREATE TABLE IF NOT EXISTS message_parts (
    part_id     TEXT PRIMARY KEY,
    message_id  TEXT NOT NULL REFERENCES messages(message_id),
    seq         INTEGER NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('text', 'tool_call', 'tool_result', 'error', 'reasoning')),
    payload     TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_parts_message_id ON message_parts(message_id);
```

### 5.4 chat_skills 表

```sql
CREATE TABLE IF NOT EXISTS chat_skills (
    chat_id     TEXT NOT NULL REFERENCES chats(chat_id),
    skill_id    TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    source      TEXT NOT NULL DEFAULT 'system',
    attached_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, skill_id)
);
```

## 6. Message Part 类型

| type | payload 格式 | 用途 |
|------|-------------|------|
| `text` | `{"content": "..."}` | 文本内容 |
| `tool_call` | `{"call_id": "...", "skill_id": "...", "name": "...", "arguments": {...}}` | 工具调用 |
| `tool_result` | `{"call_id": "...", "status": "success\|error", "output": {...}}` | 工具结果 |
| `error` | `{"error": "...", "code": "..."}` | 错误信息 |
| `reasoning` | `{"content": "..."}` | 推理摘要（预留） |

## 7. Skill Contract

### 7.1 Skill 元数据（统一模型）

```python
@dataclass
class ChatSkill:
    skill_id: str
    name: str
    description: str
    source: str          # "system" | "profile" | "workspace"
    enabled: bool
    input_schema: dict   # JSON Schema for arguments
    needs_approval: bool # 是否需要用户确认才执行
```

### 7.2 Skill 发现源

| 源 | 位置 | 说明 |
|----|------|------|
| system | `webnovel-writer/skills/*/SKILL.md` | 内置 skill 定义 |
| profile | `scripts/codex_skill_profiles/*/` | 题材 profile (xianxia, urban 等) |
| workspace | `.webnovel/skills/registry.json` | 用户安装的 workspace skill |

### 7.3 Skill 执行流程

1. Agent 在对话中发出 `tool_call`，包含 skill_id + arguments
2. 后端验证：skill 是否已挂载、参数是否符合 input_schema
3. 如果 `needs_approval=True`，暂停执行，返回 `tool_call` 事件等待前端确认
4. 执行 skill 逻辑（调用 pipeline/RAG/etc.）
5. 返回 `tool_result` 事件
6. Agent 继续推理

## 8. 非目标（Phase 2 明确不做）

1. 不做任意代码执行的插件运行时
2. 不做多租户认证/授权
3. 不做 per-token SQLite 写入（只在流完成后持久化）
4. 不做独立的 `apps/chat-ui/` 应用（在 dashboard 上扩展）
5. 不做会话级 stream 断点续传（v1 不支持 resume）
6. 不替换现有 pipeline/RAG 内部实现

## 9. 与现有模块的关系

| 现有模块 | Phase 2 角色 |
|---------|-------------|
| `GenerationAPIClient` | 扩展 streaming 能力（增加 async chunk iterator） |
| `SessionManager` | 复用 profile 发现和 session 生命周期 |
| `PipelineOrchestrator` | 作为 skill 执行的后端能力 |
| `RAGAdapter` | 作为 skill 执行的后端能力 |
| `SkillsService/manager` | 复用 workspace registry CRUD |
| `dashboard/app.py` | 新增 chat router |
| `dashboard/frontend/` | 新增 chat 页面和组件 |

## 10. 文件布局

### 新增后端文件

```
core/agent_runtime/
    __init__.py           # modify
    chat_models.py        # Chat/Message/MessagePart dataclasses
    chat_schema.py        # SQLite schema bootstrap
    chat_repository.py    # CRUD operations for chat.db
    chat_service.py       # 业务逻辑编排

core/skill_system/
    __init__.py           # modify
    chat_skill_models.py  # ChatSkill dataclass
    chat_skill_registry.py # 三源合并发现
    chat_skill_executor.py # 安全执行 + schema 验证

dashboard/
    routers/chat.py       # FastAPI chat router
    models/chat.py        # Pydantic request/response models
    services/chat/
        __init__.py
        service.py        # chat orchestration
        streaming.py      # SSE event protocol + streaming adapter
```

### 新增前端文件

```
dashboard/frontend/src/
    api/chat.js                    # Chat API client + SSE helper
    pages/ChatPage.jsx             # Chat workspace 主页面
    components/chat/
        ChatShell.jsx              # 左右布局 shell
        MessageList.jsx            # 消息列表（虚拟滚动）
        MessageBubble.jsx          # 单条消息渲染
        Composer.jsx               # 输入框 + 发送按钮
        SkillDrawer.jsx            # Skill 库侧边抽屉
        StreamRenderer.jsx         # 流式文本渲染
        ToolCallCard.jsx           # 工具调用卡片
        ToolResultCard.jsx         # 工具结果卡片
        useChatStream.js           # SSE stream hook
        useChatState.js            # Chat state reducer hook
```
