# PRD Refined（需求冻结稿）

> 日期：2026-03-27
> 来源：`docs/prd.md` + 多轮需求澄清
> 目标：把“Codex 写作工作流”收敛为可直接开发与验收的规格

## 基线说明

本稿以当前工作区（含未提交改动）作为实现基线进行约束，不回退既有本地修改。

## 1. 目标与原则

1. Dashboard 前端改为纯展示（只读），不再承担写入职责。
2. 文件写作由 Codex 直接完成，系统只负责“快速定位 + 一致性保障”。
3. 建立统一 CLI 入口，标准化 Codex 写作行为。
4. Skill 加载必须会话隔离，不能污染 Codex 全局。
5. RAG 需要达到连通性 + 正确性 + 性能（13档）验收标准。

## 2. 已确认决策（冻结）

1. 写接口处理策略：`A`（物理删除代码，不是保留空壳）。
2. 纯展示页面范围：`SkillsPage`、`SettingsPage`、`OutlineWorkspacePage`、`FilesPage`。
3. 展示策略：写操作 `UI 隐藏`（不是禁用）。
4. 新增统一命令：`是`（不是复用零散命令拼接）。
5. 索引对象：章节正文、总纲、细纲。
6. 索引策略：增量更新。
7. 触发策略：文件变更自动触发。
8. 快速定位主键：章节号、场景标签。
9. Skill 选择方式：人工选择 profile。
10. 首批 profile：战斗、描写、一致性。
11. 文档落盘：`docs/prd-refined.md`。

## 3. 范围定义

### 3.1 In Scope

1. 前端写操作入口全部移除，仅保留只读浏览。
2. 删除 Dashboard 写接口与对应服务实现。
3. 增加统一 CLI 命令（建议命名：`webnovel codex`）。
4. 建立增量索引与文件监听机制。
5. 建立会话级 Skill 装载机制（局部生效）。
6. 增加 RAG 13档验证命令与 CI 集成。

### 3.2 Out of Scope

1. 不新增在线协作编辑器。
2. 不做 Codex 全局 Skill 仓库改造。
3. 不做前端交互美化为主的改版。

## 4. 功能需求

### FR-1 前端纯展示化

1. 以下页面移除所有写入口按钮与动作绑定：
   - `SkillsPage`
   - `SettingsPage`
   - `OutlineWorkspacePage`
   - `FilesPage`
2. 页面保留只读查询能力。
3. 页面显式展示“当前为只读展示模式”。

### FR-2 删除写接口（物理删除）

1. 删除对应路由定义。
2. 删除对应 service 写逻辑实现。
3. 删除不再使用的请求/响应模型与前端 API 调用。

### FR-3 统一 Codex CLI 命令

新增入口：

```bash
webnovel codex <subcommand> ...
```

最小子命令集：

1. `webnovel codex session start --profile <battle|description|consistency> --project-root <path>`
2. `webnovel codex session stop --session-id <id>`
3. `webnovel codex index status --project-root <path>`
4. `webnovel codex rag verify --project-root <path>`

### FR-4 增量索引（章节/总纲/细纲）

1. 监听目标文件变更后自动触发增量索引。
2. 索引至少输出两类倒排：
   - 按章节号
   - 按场景标签
3. 索引状态持久化到项目内 `.webnovel`（仅项目作用域，不是全局）。

建议产物：

1. `.webnovel/codex/fast-index.json`
2. `.webnovel/codex/index-state.json`
3. `.webnovel/codex/watch-events.jsonl`

### FR-5 会话级 Skill 库

1. Skill 只在当前写作会话加载。
2. 会话结束自动清理会话 Skill 目录。
3. 禁止写入 Codex 全局 Skill 路径。
4. 支持人工选择 profile：
   - `battle`
   - `description`
   - `consistency`

建议目录：

1. 模板库：`webnovel-writer/scripts/codex_skill_profiles/`
2. 会话态：`.webnovel/codex/sessions/<session_id>/skills/`

### FR-6 RAG 13档验证

验证命令：

```bash
webnovel codex rag verify --project-root <path> --report json
```

验收分三层，全部满足才通过：

1. 连通性
   - `vectors.db` 可打开
   - `index.db` 可打开
   - `rag_schema_meta` 存在且版本合法
   - 最小检索调用可执行（不报错）
2. 正确性
   - 基准集：60 条查询（战斗20，描写20，一致性20）
   - `Hit@5 >= 0.90`
   - `MRR@10 >= 0.70`
   - 章节约束正确率 `>= 0.98`
3. 性能
   - 检索延迟 `p95 <= 700ms`（top_k=8）
   - 检索延迟 `p99 <= 1200ms`
   - 单文件增量索引 `p95 <= 1500ms`（<=10k 字）
   - 文件变更到可检索可见时间 `p95 <= 3s`

## 5. 接口变更清单（删除）

### 5.1 Dashboard API 删除项

1. `POST /api/runtime/migrate`
2. `POST /api/skills`
3. `PATCH /api/skills/{skill_id}`
4. `POST /api/skills/{skill_id}/enable`
5. `POST /api/skills/{skill_id}/disable`
6. `DELETE /api/skills/{skill_id}`
7. `POST /api/settings/files/write`
8. `POST /api/settings/dictionary/extract`
9. `POST /api/settings/dictionary/conflicts/{id}/resolve`
10. `POST /api/outlines/split/preview`
11. `POST /api/outlines/split/apply`
12. `POST /api/outlines/resplit/preview`
13. `POST /api/outlines/resplit/apply`
14. `POST /api/outlines/order/validate`
15. `POST /api/edit-assist/preview`
16. `POST /api/edit-assist/apply`
17. `GET /api/edit-assist/logs`
18. `POST /api/codex/split-dialog/open`
19. `POST /api/codex/file-edit/open`

### 5.2 前端 API 删除项

1. `skills.js` 的 create/toggle/delete 调用链。
2. `settings.js` 的 write/extract/resolve 调用链。
3. `outlines.js` 的 split/resplit/apply 调用链。
4. `OutlineWorkspacePage.jsx` 内直连 `/api/edit-assist/preview` 调用。
5. `codexBridge.js` 及页面触发入口。

## 6. 可执行改造清单

1. 删除后端写路由并清理 `app.py` 的 router 挂载。
2. 删除对应 service 写实现与无用模型。
3. 改造 4 个前端页面为只读展示。
4. 删除前端写 API 模块函数与调用。
5. 新增 `webnovel codex` 命令组与参数解析。
6. 实现文件监听 + 增量索引器。
7. 实现会话 Skill profile 装载与会话清理。
8. 实现 `rag verify` 与 JSON 报告输出。
9. 增加单测与集成测试，覆盖删除面与新增命令。
10. 更新 README/接口文档/操作手册。

## 7. 里程碑（M1/M2/M3）

### M1（只读化与删接口）

1. 交付前端 4 页面只读化。
2. 交付后端写接口物理删除。
3. 交付兼容性说明与迁移文档。

验收：前端无写入口、对应写 API 不存在、测试通过。

### M2（统一 Codex 命令 + 增量索引）

1. 交付 `webnovel codex` 命令组。
2. 交付文件变更自动触发的增量索引。
3. 交付章节号/场景标签快速定位能力。

验收：文件修改后索引自动更新，CLI 能定位目标文件。

### M3（会话 Skill + RAG 13档）

1. 交付 3 个 profile 的会话级 Skill 装载。
2. 交付 `rag verify` 全量指标。
3. 接入 CI 阻断（RAG 验证失败则失败）。

验收：Skill 不落全局、RAG 指标达标、CI 生效。

## 8. 风险与约束

1. 删除接口会影响历史脚本调用，需提供迁移提示。
2. 文件监听在不同 OS 行为差异大，需 fallback 轮询机制。
3. RAG 性能受硬件影响，CI 需固定资源档位。
4. 指标未达标时必须阻断上线，不允许“先上线后修”。

## 9. 交付物

1. 可执行改造清单（见第6节）。
2. 接口变更清单（见第5节）。
3. 分阶段里程碑（见第7节）。

