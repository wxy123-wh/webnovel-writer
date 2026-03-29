# Webnovel Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Runtime](https://img.shields.io/badge/Runtime-Codex-blue.svg)](#)

`Webnovel Writer` 是面向 Codex 的长篇网文创作系统，目标是降低 AI 写作中的"遗忘"和"幻觉"，支持长周期连载创作。

## 当前产品状态

仓库当前已经收敛出清晰方向，**可支持的商业化形态**已经明确为：**GPL v3 自托管单租户部署 + 有偿支持 / 实施服务**。现阶段产品形态仍然是：**CLI 主导写作、Dashboard 只读观察、索引与 RAG 验证作为质量门禁与交付辅助能力**。

### M1 阶段：只读化与删接口（已完成）
- 删除所有写接口（19 个端点）
- Dashboard 改为纯展示模式
- 前端 4 页面改为只读展示
- 删除前端写 API 模块

### M2 阶段：统一 CLI 入口 + 增量索引（当前商业模型下已落地）
- 实现 `webnovel codex` 统一命令入口
- 实现会话管理系统
- 实现索引状态与索引产物落盘
- 实现章节号/场景标签快速定位

### M3 阶段：会话 Skill + RAG 验证（当前商业模型下已落地）
- 实现会话级 Skill profile 装载
- 提供 `rag verify` 命令入口
- 正确性 / 性能结果必须由项目自己的 benchmark 产物提供

**详见**：`docs/ARCHITECTURE.md`

> [!IMPORTANT]
> - **Python ≥ 3.10**（使用 `X | Y` union 类型语法，低版本会抛 SyntaxError）
> - **Node.js ≥ 18**（仅在本地构建前端时需要）
> - Windows / macOS / Linux 均支持

## 文档导航

- 架构文档：`docs/ARCHITECTURE.md` ⭐ **当前阶段状态与目标架构**
- CLI 参考：`docs/CLI_REFERENCE.md` ⭐ **统一命令入口**
- 接口说明：`docs/接口.md`
- 模块说明：`docs/模块.md`
- 商业化说明：`docs/COMMERCIALIZATION.md`
- 操作手册：`docs/操作手册.md`
- Dashboard 开发：`webnovel-writer/DEVELOPMENT.md`

## 快速开始

### CLI 命令（推荐）

```bash
# 启动写作会话（加载 battle profile Skill）
python -X utf8 webnovel-writer/scripts/webnovel.py codex session start \
  --profile battle \
  --project-root /path/to/project

# 查询索引状态
python -X utf8 webnovel-writer/scripts/webnovel.py codex index status \
  --project-root /path/to/project

# 查询 RAG 当前状态
python -X utf8 webnovel-writer/scripts/webnovel.py codex rag verify \
  --project-root /path/to/project \
  --report json

# 停止会话
python -X utf8 webnovel-writer/scripts/webnovel.py codex session stop \
  --session-id session-abc123
```

**详见**：`docs/CLI_REFERENCE.md`

### 传统方式（仅用于初始化和查询）

#### 1) 安装依赖

```bash
# 生产依赖
pip install -r webnovel-writer/dashboard/requirements.txt
pip install -r webnovel-writer/scripts/requirements.txt

# 开发 / 测试依赖（额外安装）
pip install -r webnovel-writer/dashboard/requirements-dev.txt
pip install -r webnovel-writer/scripts/requirements-dev.txt
```

#### 2) 初始化项目

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py init ./webnovel-project "你的书名" "题材"
```

#### 3) 绑定工作区

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py use "<PROJECT_ROOT>" --workspace-root "<WORKSPACE_ROOT>"
```

说明：
- 工作区指针写入：`<WORKSPACE_ROOT>/.codex/.webnovel-current-project`
- 用户级 registry：`~/.codex/webnovel-writer/workspaces.json`

#### 4) 运行预检（推荐 JSON）

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<PROJECT_ROOT>" preflight --format json
```

#### 5) 常用命令

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py where
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<PROJECT_ROOT>" extract-context --chapter 1 --format text
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<PROJECT_ROOT>" status -- --focus all
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<PROJECT_ROOT>" dashboard
```

## 启动 Dashboard

### 本地开发（仅本机访问）

```bash
python -m dashboard.server --project-root /path/to/your/novel
```

Dashboard 将监听 `127.0.0.1:8765`（默认仅本机可访问）。

> [!NOTE]
> Dashboard 现已改为纯展示模式（M1 阶段）。所有写操作请使用 CLI 命令。

### 局域网访问

> [!WARNING]
> 监听 `0.0.0.0` 会使服务对局域网所有设备可见。请确保在受信任的内网环境中使用，并配置 CORS 来源。

```bash
python -m dashboard.server \
  --project-root /path/to/novel \
  --host 0.0.0.0 \
  --basic-auth writer:change-me \
  --cors-origin "http://192.168.1.100:8765"
```

### Docker 部署（运维场景）

```bash
# 构建镜像
docker build -t webnovel-dashboard .

# 运行（将 /path/to/novel 替换为你的项目路径）
docker run -d \
  --name webnovel-dashboard \
  -p 8765:8765 \
  -e WEBNOVEL_DASHBOARD_BASIC_AUTH="writer:change-me" \
  -v /path/to/novel:/project:ro \
  webnovel-dashboard \
  --log-json \
  --cors-origin "http://localhost:8765"
```

或使用 Docker Compose：

```bash
NOVEL_PROJECT_PATH=/path/to/novel \
WEBNOVEL_DASHBOARD_BASIC_AUTH="writer:change-me" \
docker compose up -d
docker compose logs -f
```

## 安全注意事项

> [!CAUTION]
> 当前 Dashboard 已支持**最小内置 Basic Auth**，可通过 `--basic-auth user:password` 或 `WEBNOVEL_DASHBOARD_BASIC_AUTH` 启用。
> 当前主线支持的商业化方式是**受信任环境中的自托管单租户部署 + 有偿支持 / 实施服务**，而不是公网多租户托管 SaaS。

- 生产环境必须通过 `--cors-origin` 指定精确来源，禁用 CORS 全开放
- 非本地 / 非单机部署至少应启用 Basic Auth；`/health` 会保持免认证，便于探针检查
- 使用 Docker 时建议以只读卷挂载（`:ro`）防止容器意外修改小说文件
- 推荐使用 `--log-json` 输出结构化日志，对接日志收集系统（如 Loki、Datadog）

## 迁移说明（历史运行时痕迹）

- 运行时主链路已统一为 `.codex`。
- 若存在历史 legacy 指针，可执行一次性迁移：

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<PROJECT_ROOT>" migrate codex --dry-run
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<PROJECT_ROOT>" migrate codex
```

说明：迁移命令会读取历史指针并收敛到 `.codex`，日常运行只使用 `.codex`。

## 常见问题 (FAQ)

### 1. 如何使用新的 CLI 命令？

详见 `docs/CLI_REFERENCE.md`。所有写作操作现已统一到 `webnovel codex` 命令组。

### 2. Dashboard 还能写入吗？

不能。M1 阶段已删除所有写接口。Dashboard 现为纯展示模式，所有写操作请使用 CLI 命令。

### 3. 如何迁移历史脚本？

如果你的脚本曾调用已删除的 HTTP API（如 `POST /api/skills`），需要迁移到 CLI。详见 `docs/ARCHITECTURE.md` 的迁移指南。

### 4. `rag verify` 输出是否已经代表发布级质量证明？

仓库内 CI 只能证明 `rag verify` 链路和 benchmark 契约本身可工作，不能直接代替客户项目的质量验收。实际商业交付时，应在目标项目中准备 `.webnovel/codex/rag-benchmark.json` 并以该项目自己的报告作为验收依据。详见 `docs/COMMERCIALIZATION.md`。

### 5. Git Push 时提示 `Connection closed by 198.18.0.x port 22`

这是由于本地代理（如 Clash/V2Ray 的 Fake-IP 模式）拦截了 SSH 默认的 22 端口导致的。
**解决方法**：修改本地的 `~/.ssh/config`，强制通过 443 端口连接 GitHub：
```ssh
Host github.com
  HostName ssh.github.com
  Port 443
  User git
  # 请确保 IdentityFile 的路径正确指向你的私钥
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
```

## 开源协议

本项目使用 `GPL v3` 协议，详见 `LICENSE`。

当前商业化模式不改变该许可证：产品以 GPL v3 继续发布，商业收入来自自托管部署、实施与支持服务。

## 贡献

欢迎提交 Issue 和 PR：

```bash
git checkout -b feature/your-feature
git commit -m "feat: add your feature"
git push origin feature/your-feature
```
