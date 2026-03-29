# 2026-03-27 Claude -> Codex 改造记录

## 目标
按 `docs/codex-desktop-only-refactor-plan.md` 执行第一阶段：将仓库中 Claude 相关路径/命名改为 Codex，并移除运行时对 Claude 的兼容读取。

## 本次改动摘要

1. 运行时单路径化（`.codex`）
- `webnovel-writer/scripts/project_locator.py`
  - 移除 `.claude` 指针读取与 `CLAUDE_*` / `WEBNOVEL_CLAUDE_HOME` 环境变量分支。
  - 指针候选仅保留 `.codex/.webnovel-current-project`。
- `webnovel-writer/scripts/data_modules/config.py`
  - 用户目录候选仅保留 Codex 相关环境变量与 `~/.codex`。
- `webnovel-writer/scripts/data_modules/context_manager.py`
  - 共享参考文件读取仅保留 `.codex/references` + 内置 references。
- `webnovel-writer/dashboard/app.py`
  - pointer 恢复仅扫描 `.codex`。
- `webnovel-writer/dashboard/server.py`
  - 启动脚本仅从 `.codex` 指针读取。

2. 插件目录与发布链路改名为 Codex
- 目录重命名：
  - `.claude-plugin` -> `.codex-plugin`
  - `webnovel-writer/.claude-plugin` -> `webnovel-writer/.codex-plugin`
- `webnovel-writer/scripts/sync_plugin_version.py`
  - 路径同步到 `.codex-plugin/*`。
  - CLI 描述改为 Codex plugin。
- `.github/workflows/plugin-version.yml`
  - 监听路径改为 `.codex-plugin/marketplace.json` 与 `webnovel-writer/.codex-plugin/plugin.json`。
- `.gitignore`
  - 忽略路径改为 `.codex` / `.codex-plugin` 对应项。

3. 文档/技能/Agent 统一替换
- `CLAUDE_PLUGIN_ROOT` -> `CODEX_PLUGIN_ROOT`
- `CLAUDE_PROJECT_DIR` -> `CODEX_PROJECT_DIR`
- “Claude Code/Claude” 文案统一替换为 Codex（仅保留迁移实现中的 legacy 常量）。
- 代表文件：
  - `webnovel-writer/agents/*.md`
  - `webnovel-writer/skills/**/*.md`
  - `webnovel-writer/references/*`
  - `webnovel-writer/templates/output/index-schema.md`
  - `README.md`

4. 参考文件改名
- `webnovel-writer/references/claude-code-call-matrix.md` -> `webnovel-writer/references/codex-code-call-matrix.md`
- `webnovel-writer/scripts/workflow_manager.py` 中引用同步更新。

5. 测试同步（与单路径策略对齐）
- `webnovel-writer/dashboard/tests/test_runtime_api.py`
  - 默认状态用 codex pointer。
- `webnovel-writer/scripts/data_modules/tests/test_project_locator.py`
  - `.claude` 指针用例改为 `.codex`。
- `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
  - references 测试改为 `.codex/references`。
- `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`
  - references 测试改为 `.codex/references`。
- `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
  - workspace pointer 测试改为 `.codex`。
- `webnovel-writer/scripts/data_modules/tests/test_codex_migration.py`
  - 改为通过迁移模块常量读取 legacy 目录名，去掉测试文件中的硬编码 `.claude`。

## 当前遗留（刻意保留）
- 仅 `webnovel-writer/scripts/migrations/codex_migration.py` 保留 `LEGACY_CONTEXT_DIR = ".claude"`。
- 目的：保留 `migrate codex` 手工迁移能力，把历史目录迁移到 `.codex`，但运行时主链路不再兼容读取 `.claude`。

## 验证情况

1. 文本扫描
- 执行：`git grep -n -i 'claude'`
- 结果：仅剩 `scripts/migrations/codex_migration.py` 的 legacy 常量一处。

2. 测试
- 通过：
  - `python -m pytest -q dashboard/tests/test_runtime_api.py -o addopts='' --basetemp <workspace_temp> -p no:inline_snapshot`
  - 结果：`4 passed`
- 受环境权限影响未完整通过：
  - 部分 `tmp_path`/缓存目录在当前环境出现 `WinError 5 (Access denied)`，导致 `project_locator` 等测试在收尾阶段报错。

## 备注
- 本次仅做增量改造，未回滚工作区中既有的其它未提交变更。
