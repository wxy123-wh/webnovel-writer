# Webnovel Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Runtime](https://img.shields.io/badge/Runtime-Agent-blue.svg)](#)

`Webnovel Writer` 的主产品形态是**对话式 Chat Agent 写作台**。仓库内仍保留 CLI、Dashboard 等能力，但现在统一围绕一个成熟的本地启动体验：**从仓库根目录启动，不要求用户了解内部模块路径**。

## 环境要求

- Python 3.10+
- Node.js 18+
- PowerShell（Windows 本地推荐）
- 可选：Docker / Docker Compose

## 本地快速开始（推荐）

### 1. 创建一个小说项目（首次运行时）

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py init ./webnovel-project "My Book" "Genre"
```

### 2. 使用唯一推荐的本地启动命令

```powershell
powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot ./webnovel-project -StartDashboard
```

这条命令会在仓库根目录完成以下工作：

- 检查 Python / Node 前端工具链
- 安装 Python 依赖
- 安装并构建 Dashboard 前端（必要时）
- 绑定当前工作区到你的小说项目
- 通过统一包装入口 `webnovel-writer/scripts/webnovel.py dashboard ...` 启动应用

启动后访问 `http://127.0.0.1:8765`。

> [!IMPORTANT]
> Chat Agent 是当前唯一推荐的主工作台。默认情况下，Dashboard 会直接进入**内置本地模式**，无需额外 API key 也可以开始对话；如果你配置了 `GENERATION_API_KEY`（或 `OPENAI_API_KEY`），则会自动切换到外部生成模式。

> [!IMPORTANT]
> 不再推荐从仓库根目录运行 `python -m dashboard.server`。那是内部模块入口，不是面向仓库用户的标准启动路径。

## 本地高级入口（保留给自动化 / 熟悉仓库的用户）

如果你已经自己管理好了依赖和前端构建，也可以直接使用统一 CLI 包装入口：

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py dashboard --project-root /path/to/your/novel
```

该入口会先检查前端构建产物是否存在，再转发到 `dashboard.server` 支持的参数，例如：

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py dashboard \
  --project-root /path/to/your/novel \
  --host 127.0.0.1 \
  --port 8765 \
  --cors-origin http://localhost:8765 \
  --log-level INFO
```

## Docker / Compose（推荐的容器路径）

### 1. 准备环境文件

```bash
cp .env.example .env
```

编辑 `.env`，至少设置：

```dotenv
NOVEL_PROJECT_PATH=/absolute/path/to/your/webnovel-project
GENERATION_API_KEY=<optional: switch Chat to external generation>
```

### 2. 启动 Compose

```bash
docker compose up --build
```

这样会：

- 将你明确指定的小说项目只读挂载到 `/project`
- 启动预构建前端的 Dashboard 容器
- 默认暴露 `http://localhost:8765`

现在 `docker-compose.yml` 不再默认回退到 `./novel-project`，避免把错误目录静默挂载进去。

## 常用 CLI 入口

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py agent run --chapter 1 --profile battle --publish --project-root /path/to/project
python -X utf8 webnovel-writer/scripts/webnovel.py codex index status --project-root /path/to/project
python -X utf8 webnovel-writer/scripts/webnovel.py codex rag verify --project-root /path/to/project --report json
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root /path/to/project preflight --format json
```

## 文档导航

- 架构文档：`docs/ARCHITECTURE.md`
- Phase 2 契约：`docs/phase2-chat-agent-contract.md`
- CLI 参考：`docs/CLI_REFERENCE.md`
- 商业化说明：`docs/COMMERCIALIZATION.md`
- 开发说明：`webnovel-writer/DEVELOPMENT.md`
- 运行脚本说明：`running/workflow.md`

## 产品定位

- **主入口：Chat Agent / Chat UI**
- **核心内核：Skill + Pipeline + RAG**
- **伴随入口：CLI**

当前 shipped 的 Dashboard 页面只保留 Chat 创作工作台这一条用户路径；CLI 继续负责自动化、索引、RAG 与运维脚本能力。

## 开源协议

本项目使用 `GPL v3` 协议，详见 `LICENSE`。
