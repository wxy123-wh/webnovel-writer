# 项目结构与运维

## 目录层级（真实运行）

在 Codex / Claude 运行下，至少有 4 层概念：

1. `WORKSPACE_ROOT`（工作区根，常见来自 `${CODEX_PROJECT_DIR}` 或 `${CLAUDE_PROJECT_DIR}`）
2. `WORKSPACE_ROOT/.codex/` 或 `WORKSPACE_ROOT/.claude/`（工作区级指针与配置）
3. `PROJECT_ROOT`（真实小说项目根，`/webnovel-init` 按书名创建）
4. `PLUGIN_ROOT`（可选：插件缓存目录，不在项目内；本地仓库模式可无此层）

### A) Workspace 目录（含 context 指针）

```text
workspace-root/
├── .codex/ 或 .claude/
│   ├── .webnovel-current-project   # 指向当前小说项目根
│   └── settings.json
├── 小说A/
├── 小说B/
└── ...
```

### B) 小说项目目录（`PROJECT_ROOT`）

```text
project-root/
├── .webnovel/            # 运行时数据（state/index/vectors/summaries）
├── 正文/                  # 正文章节
├── 大纲/                  # 总纲与卷纲
└── 设定集/                # 世界观、角色、力量体系
```

## 插件目录（Marketplace 安装，可选）

插件不在小说项目目录内，而在宿主插件缓存目录。运行时可用 `CLAUDE_PLUGIN_ROOT` 引用：

```text
${CLAUDE_PLUGIN_ROOT}/
├── skills/
├── agents/
├── scripts/
└── references/
```

### C) 用户级全局映射（兜底）

当工作区没有可用指针时，会使用用户级 registry 做 `workspace -> current_project_root` 映射：

```text
${WEBNOVEL_HOME:-${CODEX_HOME:-~/.codex}}/webnovel-writer/workspaces.json
# 兼容历史路径：${CLAUDE_HOME:-~/.claude}/webnovel-writer/workspaces.json
```

## 模拟目录实测（2026-03-03）

基于 `D:\wk\novel skill\plugin-sim-20260303-012048` 的实际结果：

- `WORKSPACE_ROOT`：`D:\wk\novel skill\plugin-sim-20260303-012048`
- 指针文件：`D:\wk\novel skill\plugin-sim-20260303-012048\.codex\.webnovel-current-project`（或 `.claude\...`）
- 指针内容：`D:\wk\novel skill\plugin-sim-20260303-012048\凡人资本论-二测`
- 已创建项目示例：`凡人资本论/`、`凡人资本论-二测/`

## 常用运维命令

统一前置（手动 CLI 场景）：

```bash
export WORKSPACE_ROOT="${CODEX_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
export SCRIPTS_DIR="${SCRIPTS_DIR:-./webnovel-writer/scripts}"
export PROJECT_ROOT="$(python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

### 索引重建

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index process-chapter --chapter 1
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index stats
```

### 健康报告

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus all
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus urgency
```

### 向量重建

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag index-chapter --chapter 1
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag stats
```

### 测试入口

```bash
pwsh "./webnovel-writer/scripts/run_tests.ps1" -Mode smoke
pwsh "./webnovel-writer/scripts/run_tests.ps1" -Mode full
```
