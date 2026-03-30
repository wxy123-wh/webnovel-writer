# Webnovel Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Runtime](https://img.shields.io/badge/Runtime-Agent-blue.svg)](#)

`Webnovel Writer` 的唯一主产品形态定义为：**对话式 Chat Agent 写作台**。

用户与 Agent 对话推进创作；Skill 库按会话装载；内部固定沿用“大纲 → 剧情 → 事件 → 场景 → 整章整合”的流水线；RAG 索引与验证负责长篇小说的一致性保障。自本阶段起，项目不再把 CLI、Dashboard、VS Code 插件或历史 Codex / ClaudeCode 形态视为主产品入口。

## 当前产品定义

当前主线支持的商业化形态仍为：**GPL v3 自托管单租户部署 + 有偿支持 / 实施服务**。但产品形态已经收敛为：

1. **主入口：Chat Agent / Chat UI**
   - 唯一面向用户的主产品形态
   - 用户通过对话驱动写作、审阅、风格切换和流程推进
2. **核心内核：Skill + Pipeline + RAG**
   - Skill 库：支持不同题材/风格/能力的会话级装载
   - Pipeline：固定保持大纲 → 剧情 → 事件 → 场景 → 整章整合
   - RAG：负责检索、验证和一致性约束
3. **伴随界面：CLI / Dashboard / VS Code Companion**
   - CLI：自动化、运维、脚本入口
   - Dashboard：只读观察与诊断面
   - VS Code：只读 companion，不定义主产品形态

> [!IMPORTANT]
> Phase 2 已实现 Chat Agent 主入口。Dashboard 现在包含完整的对话式写作界面（Chat UI）、Skill 库管理和 SSE 流式响应。详见 `docs/phase2-chat-agent-contract.md`。

## 文档导航

- 架构文档：`docs/ARCHITECTURE.md`
- Phase 2 契约：`docs/phase2-chat-agent-contract.md`
- Phase 1 冻结稿：`docs/prd-refined.md`
- 模块说明：`docs/模块.md`
- 接口说明：`docs/接口.md`
- CLI 参考：`docs/CLI_REFERENCE.md`
- 商业化说明：`docs/COMMERCIALIZATION.md`

## 运行时现状

当前仓库已经存在的运行能力主要包括：

- **Chat Agent / Chat UI**：主产品入口，对话式写作台
- `webnovel agent`：Agent 命令面（companion）
- `webnovel codex`：会话、索引、RAG 等运维命令面（companion）
- `dashboard`：包含 Chat Agent UI + 只读观察面
- `vscode-extension`：只读 companion

这些能力在 Phase 1 中继续保留，但它们的定位已经统一调整为：**服务 Chat Agent 主产品，而不是各自独立定义产品形态**。

## Chat Agent（主入口）

```bash
# 启动 Dashboard（包含 Chat Agent UI）
python -m dashboard.server --project-root /path/to/your/novel

# 浏览器访问 http://localhost:8765，默认进入 Chat 页面
```

Chat Agent 功能：
- 对话式写作：通过自然语言驱动创作
- 流式响应：Agent 回复实时流式渲染
- Skill 库：按会话装载题材/风格/能力
- 消息历史：自动持久化，刷新不丢失

### Chat API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/chat/chats` | 列出所有对话 |
| `POST` | `/api/chat/chats` | 创建新对话 |
| `GET` | `/api/chat/chats/{id}` | 获取对话详情 |
| `DELETE` | `/api/chat/chats/{id}` | 删除对话 |
| `GET` | `/api/chat/chats/{id}/messages` | 获取消息历史 |
| `POST` | `/api/chat/chats/{id}/messages` | 发送消息（非流式） |
| `POST` | `/api/chat/chats/{id}/stream` | 发送消息（SSE 流式） |
| `GET` | `/api/chat/skills` | 列出可用 Skills |
| `PATCH` | `/api/chat/chats/{id}/skills` | 更新 Skill 挂载 |

## 当前可用的伴随入口

### CLI（运维 / 自动化）

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py agent run --chapter 1 --profile battle --publish --project-root /path/to/project
python -X utf8 webnovel-writer/scripts/webnovel.py codex index status --project-root /path/to/project
python -X utf8 webnovel-writer/scripts/webnovel.py codex rag verify --project-root /path/to/project --report json
```

### Dashboard（只读观察）

```bash
python -m dashboard.server --project-root /path/to/your/novel
```

### VS Code Companion（只读）

位于 `webnovel-writer/vscode-extension/`，仅承担项目浏览与辅助观察，不替代主入口。

## 仓库收敛方向

目标模型统一为：

```text
core/
  agent_runtime/
  skill_system/
  pipeline/
  rag_index/
  project_state/
apps/
  chat-ui/
  cli/
  dashboard/
  vscode-companion/
```

当前仓库尚未完成该目录迁移，但自本阶段起，所有新增叙事和后续重构都以该模型为准。

## 开源协议

本项目使用 `GPL v3` 协议，详见 `LICENSE`。
