# Webnovel Writer 架构文档（Phase 2 更新版）

## 概述

Webnovel Writer 的唯一主产品形态定义为：**对话式 Chat Agent 写作台**。

用户与 Agent 对话推进小说创作；Skill 库按会话装载；内部固定沿用“大纲 → 剧情 → 事件 → 场景 → 整章整合”的流水线；RAG 索引与验证负责长篇小说的一致性保障。CLI、Dashboard、VS Code 插件与历史 Codex / ClaudeCode 形态不再作为主产品入口定义，只保留 companion / ops surface 角色。

## 目标架构模型

Phase 1 的目标不是立即完成大规模代码搬迁，而是统一后续架构演进方向。目标模型如下：

```text
core/
├── agent_runtime/   # 对话会话、上下文装配、消息编排
├── skill_system/    # skill 安装、启用、会话挂载、元数据
├── pipeline/        # 大纲→剧情→事件→场景→整章整合
├── rag_index/       # 索引、检索、验证、一致性检查
└── project_state/   # 项目绑定、运行时状态、工作区元信息

apps/
├── chat-ui/         # 唯一主产品入口
├── cli/             # 自动化 / 运维 / 脚本入口
├── dashboard/       # 只读观察与诊断面
└── vscode-companion/# 编辑器伴随工具
```

## 角色边界

### 1. 主产品入口：Chat Agent / Chat UI

- 唯一面向用户的主产品形态
- 负责用户对话、任务表达、当前会话状态展示
- 调用 core 层能力完成写作推进

### 2. 核心能力：Skill + Pipeline + RAG

- `agent_runtime`：对话状态与运行时编排
- `skill_system`：Skill 库、安装、启用、会话挂载
- `pipeline`：固定创作流程推进
- `rag_index`：一致性支撑与验证
- `project_state`：项目根、工作区、运行元信息

### 3. Companion / Ops Surfaces

- **CLI**：用于自动化、运维、脚本化调用
- **Dashboard**：只读观察、诊断、数据确认
- **VS Code Companion**：只读浏览和跳转辅助

这些入口可以继续存在，但不能再反向定义产品形态。

## 当前仓库与目标模型的映射

当前代码仍主要分布在以下路径：

- `webnovel-writer/scripts/`：现有 CLI、Agent、运行时模块
- `webnovel-writer/dashboard/`：只读 Dashboard 与 HTTP API
- `webnovel-writer/vscode-extension/`：VS Code companion
- `webnovel-writer/skills/` / `scripts/codex_skill_profiles/`：现有 skill 资产

在 Phase 1 中，这些路径继续保留；它们只是向目标模型过渡时的当前承载位置，而不是最终边界定义。

## 当前运行能力的定位

### Agent 命令面

现有 `webnovel agent` 命令面承载当前 Agent 运行能力，但它在 Phase 1 中被重新定位为 **Chat Agent 主产品的现有运行时接口**，而不是长期产品形态本身。

### Codex 命令面

现有 `webnovel codex` 继续保留，用于：

- 会话生命周期
- 索引状态查询
- RAG 验证

它属于 **companion / ops surface**，不再定义主入口。

### Dashboard

Dashboard 的职责固定为：

- 只读聚合视图
- 项目观察
- 运行时诊断

不承担主写作入口，不承担 skill 管理主入口，不承担产品主叙事。

### VS Code Companion

VS Code 插件固定为只读 companion，不承担主流程。

## 核心数据流

### 写作主路径（目标形态）

```text
User
  ↓
Chat UI / Chat Agent
  ↓
Agent Runtime
  ↓
Skill System + Pipeline
  ↓
RAG Index / Verifier
  ↓
Project Files / Runtime State
```

### Companion 路径

```text
CLI / Dashboard / VS Code Companion
  ↓
调用或读取 core 层能力
  ↓
仅承担运维、观察、诊断、跳转
```

## Phase 2 已交付能力

Phase 2 在现有 `dashboard/` 上实现了 Chat Agent 主入口：

### 后端新增

| 模块 | 文件 | 用途 |
|------|------|------|
| Chat 持久化 | `core/agent_runtime/chat_models.py` | Chat/Message/MessagePart 数据类 |
| Chat 持久化 | `core/agent_runtime/chat_schema.py` | SQLite schema bootstrap |
| Chat 持久化 | `core/agent_runtime/chat_repository.py` | CRUD 操作 |
| Chat 持久化 | `core/agent_runtime/chat_service.py` | 业务逻辑编排 |
| Chat API | `dashboard/routers/chat.py` | FastAPI 路由 (10 个端点) |
| Chat API | `dashboard/models/chat.py` | Pydantic 请求/响应模型 |
| Chat 服务 | `dashboard/services/chat/service.py` | 对话编排服务 |
| Chat 服务 | `dashboard/services/chat/streaming.py` | SSE 事件协议 + 流式适配器 |
| Skill 注册 | `core/skill_system/chat_skill_registry.py` | 三源合并 Skill 发现 |
| Skill 注册 | `core/skill_system/chat_skill_models.py` | ChatSkill 数据类 |

### 前端新增

| 组件 | 文件 | 用途 |
|------|------|------|
| API 客户端 | `src/api/chat.js` | Chat API fetch 封装 + SSE |
| 状态管理 | `src/components/chat/useChatState.js` | Chat state reducer |
| 流式 Hook | `src/components/chat/useChatStream.js` | SSE stream hook |
| 消息渲染 | `src/components/chat/MessageBubble.jsx` | 消息气泡 (text/tool/error) |
| 消息列表 | `src/components/chat/MessageList.jsx` | 消息滚动区域 |
| 输入框 | `src/components/chat/Composer.jsx` | 消息输入 |
| Skill 抽屉 | `src/components/chat/SkillDrawer.jsx` | Skill 库管理面板 |
| Chat Shell | `src/components/chat/ChatShell.jsx` | 主布局容器 |
| Chat 页面 | `src/pages/ChatPage.jsx` | 对话列表 + 工作区 |

### 数据存储

- `.webnovel/chat.db` — SQLite，包含 chats、messages、message_parts、chat_skills 四张表
- 7 种 SSE 事件类型：message_start、text_delta、tool_call、tool_result、message_complete、message_error、heartbeat

### 契约文档

完整 API 契约、数据库 Schema、Skill Contract 和非目标定义见 `docs/phase2-chat-agent-contract.md`。

## 当前阶段的收敛约束

1. 所有新叙事必须把 Chat Agent 作为唯一主产品形态。
2. 所有 companion surface 只能引用 core 能力，不能再各自发展产品语义。
3. 不再把 `codex`、`dashboard`、`vscode-extension`、历史插件形态写成并列主入口。
4. Pipeline 固定保持大纲 → 剧情 → 事件 → 场景 → 整章整合。
5. RAG 继续承担一致性与验证底座角色。

## 当前阶段不做的事

1. 不做任意代码执行的插件运行时。
2. 不做多租户认证/授权。
3. 不做独立的 `apps/chat-ui/` 应用（在 dashboard 上扩展）。
4. 不做会话级 stream 断点续传。
5. 不把 Dashboard 或 VS Code 插件重新抬回主入口。
