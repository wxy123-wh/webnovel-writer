# 2026-03-27 Codex 长时任务 Harness 设计

## 背景
- 依据 Anthropic《Effective harnesses for long-running agents》与其 autonomous-coding quickstart。
- 核心迁移点：初始化会话 + 增量开发会话 + 结构化进度与测试工件。

## 本次落地要点
- 新建 `log/` 目录（之前不存在）。
- 设计 Codex 版流程：
  - Session 0 初始化：创建 feature_list.json / init 脚本 / progress 文件 / 初始 commit。
  - Session N 开发：每次只做一个 feature，先回归再开发，完成后提交并写进度。
  - 质量门禁：端到端验证后才将 passes=false 改为 true，禁止改 feature 描述与步骤。
  - 上下文恢复：每次先读 git log、progress、feature_list、最近 log。
- 结合本仓规范：
  - 修改前读 `log` 最近 md；修改后写 log。
  - 涉及结构/接口变更时优先 `query_graph.py` 与 `.nexus-map` 同步评估。

## 后续可执行项
- 将该流程固化为仓库内 `docs/codex-harness.md`（如需要）。
- 可继续补充 Codex 的“初始化提示词”和“续跑提示词”模板文件。
