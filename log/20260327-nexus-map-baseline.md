# 2026-03-27 nexus-map baseline & prd-clarification prep

## 本次关键改动

1. 新增 `.nexus-map/` 基线知识库文件：
   - `.nexus-map/INDEX.md`
   - `.nexus-map/arch/systems.md`
   - `.nexus-map/arch/dependencies.md`
   - `.nexus-map/arch/test_coverage.md`
   - `.nexus-map/concepts/concept_model.json`
   - `.nexus-map/concepts/domains.md`
   - `.nexus-map/hotspots/git_forensics.md`
   - `.nexus-map/raw/ast_nodes.json`
   - `.nexus-map/raw/file_tree.txt`
   - `.nexus-map/raw/git_stats.json`

2. 运行 `nexus-mapper` 过程中的环境处理：
   - 发现 `tree_sitter_language_pack` 默认缓存目录不可写导致 `LanguageNotFoundError`。
   - 将缓存目录重定向到仓库内 `.nexus-map/.ts-pack`，并下载所需语言包后成功生成 AST 原始数据。
   - 为避免噪声目录污染结构图，提取 AST 时排除了 `.worktrees`、`__temp__`、`.work`、`.venv-run`、`.venv2`。

3. 输出特征与证据缺口：
   - AST 覆盖语言：`python`, `javascript`。
   - 当前依赖图的内部 import 关系较稀疏，系统级依赖关系在文档中采用“代码导入+router 挂载”人工校验补充。
   - git 热点主要落在历史 `.claude/*` 路径，已在 `.nexus-map/hotspots/git_forensics.md` 标注风险解释。

## 对当前 PRD 澄清的价值

- 已将“前端纯展示、Codex 流程标准化、会话级 skill 加载、RAG 可用性验证”映射到明确系统边界与入口点。
- 下一轮可直接按模块问到“保留/下线接口、验收口径、迁移策略、测试阻断级别”等实施细节。
