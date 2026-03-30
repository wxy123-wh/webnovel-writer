# Webnovel Writer CLI 参考手册（Companion / Ops Surface）

## 概述

本文件描述的是 **CLI 伴随入口**，不是主产品入口。

自 Phase 1 起，Webnovel Writer 的唯一主产品形态定义为 **Chat Agent / Chat UI**。CLI 继续保留，但其职责固定为：自动化、运维、脚本调用、状态查询与兼容既有运行时能力。

## CLI 的定位

- **不是** 主写作形态
- **不是** 产品首页定义
- **是** 运行时与运维 companion surface

当前 CLI 仍然暴露两类命令面：

1. `webnovel agent`
   - 现有 Agent 运行时接口
2. `webnovel codex`
   - 会话、索引、RAG 等兼容运行时接口

## 当前可用命令

### 1. Agent 运行命令

```bash
webnovel agent run --chapter 1 --profile battle --publish --project-root /path/to/project
webnovel agent session start --profile battle --project-root /path/to/project
webnovel agent session stop --session-id session-abc123def456 --project-root /path/to/project
```

### 2. Codex 兼容运行命令

```bash
webnovel codex session start --profile battle --project-root /path/to/project
webnovel codex session stop --session-id session-abc123def456
webnovel codex index status --project-root /path/to/project
webnovel codex rag verify --project-root /path/to/project --report json
```

## 使用原则

1. 如果你在定义产品形态，请回到 Chat Agent / Chat UI。
2. 如果你在做脚本化、运维或兼容调用，请使用 CLI。
3. 不再把 CLI 作为项目的唯一或默认产品入口叙事。

## 现有 Profiles / Skills 资产

当前命令面仍可使用现有 profile：

- `battle`
- `description`
- `consistency`
- `xianxia`
- `urban`
- `mystery`
- `apocalypse`
- `romance`

这些 profile 在当前仓库阶段仍由现有目录自动发现；后续将统一收敛到 `skill_system` 的目标模型中。

## 说明

本文件保留命令参考的原因，是为了支持当前仓库阶段仍存在的自动化与运维链路。它不改变主产品已经收敛为 Chat Agent 的事实。
