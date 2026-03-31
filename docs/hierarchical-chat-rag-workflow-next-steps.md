# Hierarchical Chat + RAG Workflow 未完成事项交接

本文档用于记录当前这轮开发里**还没有改完**或**还没有完成主代理验收**的部分，留待下次继续。

## 当前总体状态

- 已完成并主代理验收：Task 1 ~ Task 7
- 已有人报告完成、但**还未完成主代理验收**：Task 8
- 还未开始：Task 9、Task 10、Final Verification Wave

当前主计划文件：

- `.sisyphus/plans/hierarchical-chat-rag-workflow.md`

## 已完成范围（下次不用重复做）

以下能力已经实现并在主流程里被确认：

1. 单书模型、严格层级与领域约束
   - `大纲 -> 剧情 -> 事件 -> 场景 -> 章节`
   - 仅允许从直接父级拆分到下一级
   - 单项目单书根节点
   - 乐观锁、受保护删除、同级排序
2. 关键层版本体系
   - 大纲、剧情、章节、设定支持 revision / diff / rollback-as-new-head
3. Proposal 审核流
   - AI 生成的结构拆分和设定抽取先进入 proposal
   - 必须 confirm 后才真正写入
4. 后端 hierarchy / review / revision API
5. RAG 重建编排基础
   - 变更后标记 stale
   - 手动触发 rebuild
   - generation 防止旧构建覆盖新状态
6. Chat 与 hierarchy 深度绑定
   - chat 请求支持 workflow payload
   - 仅允许 immediate-child 类型生成
   - chapter 修改走 proposal，不直接覆盖
7. Skill 库 Web CRUD + 独立 Skills Tab
   - 新建 / 列表 / 删除 workspace skill
   - 删除时会处理 chat 中的 workspace skill 挂载

## 还未改完 / 还未验收的部分

### Task 8：Hierarchy Workspace / Review / Revision UI

状态：**子代理报告已完成，但主代理尚未完整验收，不能直接视为完成**。

计划要求见：

- `.sisyphus/plans/hierarchical-chat-rag-workflow.md` 中 Task 8

Task 8 目标：

- 用集成式 authoring workspace 替换当前只读/分散的编辑体验
- 支持 hierarchy 节点导航
- 支持 outline / plot / event / scene / chapter / setting 的查看与编辑
- 支持 proposal 预览、confirm、reject
- 支持 revision history、diff、rollback
- UI 中明确显示 stale / conflict / version mismatch

#### 已报告改动（下次先核实）

以下文件被报告改动，但还没有全部由主代理逐个读代码并验收：

- `webnovel-writer/dashboard/frontend/src/pages/OutlineWorkspacePage.jsx`
- `webnovel-writer/dashboard/frontend/src/pages/OutlineWorkspacePage.test.jsx`
- `webnovel-writer/dashboard/frontend/src/api/authoring.js`
- `webnovel-writer/dashboard/frontend/src/api/authoring.test.js`
- `webnovel-writer/dashboard/frontend/src/App.jsx`
- `webnovel-writer/dashboard/frontend/src/App.test.jsx`
- `webnovel-writer/dashboard/frontend/src/index.css`
- `webnovel-writer/dashboard/frontend/package.json`
- `webnovel-writer/dashboard/routers/hierarchy.py`
- `webnovel-writer/dashboard/services/hierarchy.py`
- `webnovel-writer/dashboard/tests/test_hierarchy_api.py`

#### Task 8 下次建议先做的验收动作

1. 通读上面列出的 Task 8 相关文件，确认实现范围是否真的覆盖计划要求。
2. 验证是否真的存在并可用：
   - hierarchy workspace 页面
   - proposal confirm / reject UI
   - revision history / diff / rollback UI
   - chapter / setting 编辑能力
   - stale/conflict 错误提示
3. 跑前端相关测试与后端层级 API 测试。
4. 如果能启动前后端，做一次真实页面验证，至少覆盖：
   - 进入 workspace
   - 选择节点
   - proposal 审核
   - revision 保存与查看
5. 只有在主代理确认“功能覆盖 + 测试通过 + 基本交互可用”后，才能把 Task 8 标成完成。

#### Task 8 当前已知风险

- 之前只做到了“页面能打开”的部分验证，**没有完成完整后端联通验收**。
- 预览前端环境下，`/api/hierarchy/workspace` 的真实数据联调没有完全确认。
- 子代理自报完成不能替代主代理验收。

### Task 9：一键重建 RAG 索引的 Web 控件与状态 UX

状态：**未开始**。

计划要求见：

- `.sisyphus/plans/hierarchical-chat-rag-workflow.md` 中 Task 9

需要完成：

- 在 Web UI 暴露一键 reset / reindex 控件
- 展示 persisted backend truth 对应的状态：stale / building / fresh / error
- 展示 active generation、last build metadata、失败/重试状态
- 处理重复点击冲突和 retry UX

建议实现前置条件：

- 必须先把 Task 8 验收完成，否则 UI 工作台还不稳定

建议关注文件：

- `webnovel-writer/dashboard/frontend/src/pages/OutlineWorkspacePage.jsx`
- `webnovel-writer/dashboard/frontend/src/pages/SettingsPage.jsx`
- `webnovel-writer/dashboard/watcher.py`
- `webnovel-writer/dashboard/services/hierarchy.py`
- `webnovel-writer/dashboard/routers/hierarchy.py`

### Task 10：端到端加固、确定性测试替身、迁移/回填安全

状态：**未开始**。

计划要求见：

- `.sisyphus/plans/hierarchical-chat-rag-workflow.md` 中 Task 10

需要完成：

- deterministic fake AI / RAG adapters
- migration / backfill tests
- crash / retry / idempotency tests
- hierarchy CRUD、chat-assisted generation、proposal review、revision、skill CRUD、reindex 的完整回归覆盖

这一步本质是“收口”和“防翻车”，应放在 Task 8、Task 9 之后做。

## 最终验收波次（还完全没开始）

计划中要求在所有实现任务都结束后，再跑最终验收波次：

- F1. Plan Compliance Audit
- F2. Code Quality Review
- F3. Real Manual QA
- F4. Scope Fidelity Check

注意：在计划里，这一轮验收完成后，**还需要用户明确 okay 才能视为整个任务完成**。

## 已知仓库噪音 / 非本轮新增问题

这些问题之前已经确认存在，后续继续时不要误判为本轮改动引入：

- 更大范围的 `python -m pytest --no-cov` 存在既有失败：
  - `scripts/data_modules/tests/test_pipeline_cli.py`
  - `scripts/data_modules/tests/test_agent_cli.py`
- `dashboard/app.py` 存在既有 basedpyright / import-resolution 噪音
- 直接 `python -c` 启动 `dashboard.app` 可能碰到既有 `runtime_compat` import-path 问题

## 下次继续时的推荐顺序

1. 先核验 Task 8 的实际代码与测试，不要直接相信“已完成”报告。
2. 如果 Task 8 有缺口，先补齐并重新验收。
3. Task 8 完成后，再做 Task 9 的 reindex UI。
4. 然后完成 Task 10 的测试替身、迁移/回归加固。
5. 最后再进入 F1 ~ F4 最终验收波次。

## 关键文件索引

### 计划与状态

- `.sisyphus/plans/hierarchical-chat-rag-workflow.md`
- `.sisyphus/boulder.json`

### 已完成的后端核心

- `webnovel-writer/core/book_hierarchy/`
- `webnovel-writer/dashboard/models/hierarchy.py`
- `webnovel-writer/dashboard/services/hierarchy.py`
- `webnovel-writer/dashboard/routers/hierarchy.py`
- `webnovel-writer/dashboard/models/chat.py`
- `webnovel-writer/dashboard/routers/chat.py`
- `webnovel-writer/dashboard/services/chat/service.py`
- `webnovel-writer/core/skill_system/chat_skill_registry.py`

### 已完成的测试

- `webnovel-writer/scripts/data_modules/tests/test_book_hierarchy.py`
- `webnovel-writer/scripts/data_modules/tests/test_book_hierarchy_revisions.py`
- `webnovel-writer/dashboard/tests/test_hierarchy_api.py`
- `webnovel-writer/dashboard/tests/test_chat_api.py`
- `webnovel-writer/dashboard/tests/test_skills_api.py`

### Task 8 重点验收文件

- `webnovel-writer/dashboard/frontend/src/pages/OutlineWorkspacePage.jsx`
- `webnovel-writer/dashboard/frontend/src/pages/OutlineWorkspacePage.test.jsx`
- `webnovel-writer/dashboard/frontend/src/api/authoring.js`
- `webnovel-writer/dashboard/frontend/src/api/authoring.test.js`
- `webnovel-writer/dashboard/frontend/src/App.jsx`
- `webnovel-writer/dashboard/frontend/src/App.test.jsx`
- `webnovel-writer/dashboard/frontend/src/index.css`
- `webnovel-writer/dashboard/frontend/package.json`

## 文档用途说明

如果下次继续这条需求，优先先看：

1. 本文档
2. `.sisyphus/plans/hierarchical-chat-rag-workflow.md`
3. Task 8 相关代码文件

这样可以直接从“未验收的 UI 工作台”继续，而不是重新梳理整个项目背景。
