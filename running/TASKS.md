# Running Task List（PRD-Refined → Codex 开发队列）

> 生成时间：2026-03-28  
> 来源：`docs/prd-refined.md`  
> 队列文件：`running/feature_list.json`

## 队列总览

| ID | 里程碑 | 优先级 | 风险 | 标题 | 状态 |
|----|--------|--------|------|------|------|
| T001 | M1 | 1 | medium | M1 read-only contract and shared indicator | pending |
| T002 | M1 | 2 | high | M1 SkillsPage read-only conversion | pending |
| T003 | M1 | 3 | high | M1 SettingsPage read-only conversion | pending |
| T004 | M1 | 4 | high | M1 OutlineWorkspacePage read-only conversion | pending |
| T005 | M1 | 5 | medium | M1 FilesPage read-only conversion | pending |
| T006 | M1 | 6 | critical | M1 remove dashboard write routes (runtime/skills/settings) | pending |
| T007 | M1 | 7 | critical | M1 remove dashboard write routes (outlines/edit-assist/codex) | pending |
| T008 | M1 | 8 | high | M1 acceptance gate and migration notes | pending |
| T009 | M2 | 9 | high | M2 add unified webnovel codex command group | pending |
| T010 | M2 | 10 | high | M2 implement codex session start/stop | pending |
| T011 | M2 | 11 | high | M2 implement project-scoped index status artifacts | pending |
| T012 | M2 | 12 | high | M2 file watcher and incremental auto-index | pending |
| T013 | M2 | 13 | medium | M2 fast lookup by chapter number and scene tag | pending |
| T014 | M3 | 14 | critical | M3 session-scoped skill profile loader | pending |
| T015 | M3 | 15 | critical | M3 implement codex rag verify metrics command | pending |
| T016 | M3 | 16 | high | M3 CI gate and final acceptance package | pending |

---

## M1：只读化与删接口（T001–T008）

### T001 · M1 read-only contract and shared indicator

**优先级**：1 | **风险**：medium

**目标**：建立共用只读展示契约和 UI 提示组件，供 4 个页面统一引用。

**步骤**：
1. 创建共用 read-only mode helper 和提示文案
2. 将 helper 接入页面脚手架或公共 layout
3. 确保写意图 UI 分支受 read-only 契约门控

**验收命令**：
```
cd webnovel-writer/dashboard/frontend && npm run build
cd webnovel-writer/dashboard/frontend && npm test -- --runInBand
```
**验收检查**：frontend build 成功；shared read-only hint 在目标页面渲染；helper 接入后无运行时错误

---

### T002 · M1 SkillsPage read-only conversion

**优先级**：2 | **风险**：high

**目标**：从 SkillsPage 移除 create/enable/disable/delete 入口，保留读取列表和详情渲染。

**步骤**：
1. 移除写入按钮和 handlers
2. 删除 skills 页面流中的前端写 API 调用
3. 保留读取调用和 loading/error 状态

**验收命令**：
```
cd webnovel-writer/dashboard/frontend && npm run build
Playwright MCP checklist: SkillsPage read-only
```
**验收检查**：SkillsPage 无写控件；skill list 正常渲染；只读提示可见

---

### T003 · M1 SettingsPage read-only conversion

**优先级**：3 | **风险**：high

**目标**：从 SettingsPage 移除 settings write、dictionary extract、conflict resolve 动作，保留浏览能力。

**步骤**：
1. 隐藏 write/extract/resolve 控件
2. 移除关联 handlers 和 mutation 请求
3. 保留 tree 和 dictionary 读取渲染

**验收命令**：
```
cd webnovel-writer/dashboard/frontend && npm run build
Playwright MCP checklist: SettingsPage read-only
```
**验收检查**：SettingsPage 无写动作；文件树和字典读取正常；无 mutation 网络请求

---

### T004 · M1 OutlineWorkspacePage read-only conversion

**优先级**：4 | **风险**：high

**目标**：从 OutlineWorkspacePage 移除 split/resplit/apply/edit-assist 写入口，保留只读可视化。

**步骤**：
1. 隐藏 split/resplit/apply UI 控件
2. 移除 edit-assist 写触发器
3. 保持大纲读取浏览完整

**验收命令**：
```
cd webnovel-writer/dashboard/frontend && npm run build
Playwright MCP checklist: OutlineWorkspacePage read-only
```
**验收检查**：无 split/resplit/apply 控件；大纲数据正常展示；无 edit-assist mutation 请求

---

### T005 · M1 FilesPage read-only conversion

**优先级**：5 | **风险**：medium

**目标**：从 FilesPage 移除 codex 启动和其他写意图动作，保留文件树读取导航。

**步骤**：
1. 隐藏 split-dialog 和 file-edit 启动控件
2. 移除 FilesPage 中的 codex bridge mutation 调用
3. 保留文件树和文件读取交互

**验收命令**：
```
cd webnovel-writer/dashboard/frontend && npm run build
Playwright MCP checklist: FilesPage read-only
```
**验收检查**：FilesPage 无 codex 启动控件；文件树和内容预览正常；只读模式标签可见

---

### T006 · M1 remove dashboard write routes (runtime/skills/settings)

**优先级**：6 | **风险**：critical

**目标**：物理删除 runtime migrate、skills mutate、settings write/extract/resolve 端点。

**删除目标**：
- `POST /api/runtime/migrate`
- `POST /api/skills`、`PATCH /api/skills/{id}`、`POST /api/skills/{id}/enable`、`POST /api/skills/{id}/disable`、`DELETE /api/skills/{id}`
- `POST /api/settings/files/write`、`POST /api/settings/dictionary/extract`、`POST /api/settings/dictionary/conflicts/{id}/resolve`

**步骤**：
1. 删除 router 中的路由定义
2. 移除仅被删除路由使用的请求模型和 handlers
3. 确保删除的端点返回 404

**验收命令**：
```
cd webnovel-writer/dashboard && pytest tests/test_runtime_api.py tests/test_skills_api.py tests/test_settings_dictionary_api.py
```
**验收检查**：删除的写端点不可达；读端点仍返回 200；router import graph 有效

---

### T007 · M1 remove dashboard write routes (outlines/edit-assist/codex) and dead services

**优先级**：7 | **风险**：critical

**目标**：物理删除 outlines/edit-assist/codex 写端点，清理无引用 service/model 代码。

**删除目标**：
- `POST /api/outlines/split/preview`、`POST /api/outlines/split/apply`
- `POST /api/outlines/resplit/preview`、`POST /api/outlines/resplit/apply`
- `POST /api/outlines/order/validate`
- `POST /api/edit-assist/preview`、`POST /api/edit-assist/apply`、`GET /api/edit-assist/logs`
- `POST /api/codex/split-dialog/open`、`POST /api/codex/file-edit/open`

**步骤**：
1. 删除 outlines 和 edit-assist mutation 路由
2. 删除 codex bridge 写路由
3. 移除死代码 services/models 和 router 挂载

**验收命令**：
```
cd webnovel-writer/dashboard && pytest tests/test_outlines_split_api.py tests/test_outlines_resplit_api.py tests/test_edit_assist_api.py tests/test_codex_bridge_api.py
```
**验收检查**：所有 PRD 列出的写 API 已移除；只读 API 仍健康；dashboard app 无 import 错误启动

---

### T008 · M1 acceptance gate and migration notes

**优先级**：8 | **风险**：high

**目标**：M1 完整验收，确认只读 UX、后端 API 删除、迁移指南。

**步骤**：
1. 运行 dashboard 后端只读契约测试
2. 运行前端 build 并捕获 Playwright 证据
3. 记录端点删除和迁移说明文档

**验收命令**：
```
cd webnovel-writer/dashboard && pytest tests
cd webnovel-writer/dashboard/frontend && npm run build
Playwright MCP checklist: M1 full acceptance
```
**验收检查**：前端 4 页面无写入口；删除的后端写 API 不存在；迁移说明存在于 docs

---

## M2：统一 Codex 命令 + 增量索引（T009–T013）

### T009 · M2 add unified webnovel codex command group

**优先级**：9 | **风险**：high

**目标**：将 codex 暴露为一流 CLI 命令组，带确定性 help 和参数验证。

**步骤**：
1. 添加 codex 命令组解析器
2. 为 session/index/rag 注册子命令 stub
3. 确保 help 文档描述必需参数

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py --help
python -X utf8 webnovel-writer/scripts/webnovel.py codex --help
```
**验收检查**：`webnovel --help` 列出 codex；`webnovel codex --help` 成功；无效子命令返回非零退出码并带指引

---

### T010 · M2 implement codex session start/stop

**优先级**：10 | **风险**：high

**目标**：实现带 profile 选择（battle/description/consistency）的 session start/stop 与 session 元数据生命周期。

**步骤**：
1. 实现 session start 命令并返回 session id
2. 实现 session stop 命令和清理 hooks
3. 将 session 元数据持久化到项目作用域 `.webnovel/codex`

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py codex session start --profile battle --project-root <PROJECT_ROOT>
python -X utf8 webnovel-writer/scripts/webnovel.py codex session stop --session-id <SESSION_ID> --project-root <PROJECT_ROOT>
```
**验收检查**：session start 返回合法 session id；session stop 接受 session id 并退出 0；元数据写入项目作用域

---

### T011 · M2 implement project-scoped index status artifacts

**优先级**：11 | **风险**：high

**目标**：实现索引状态持久化和 `.webnovel/codex` 下的标准 codex 索引文件。

**产物**：`.webnovel/codex/fast-index.json`、`.webnovel/codex/index-state.json`

**步骤**：
1. 创建/维护 `fast-index.json`
2. 创建/维护 `index-state.json`
3. 暴露 index status 命令输出

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py codex index status --project-root <PROJECT_ROOT>
```
**验收检查**：index status 命令返回确定性 JSON；两个 artifact 文件存在于 `.webnovel/codex`

---

### T012 · M2 file watcher and incremental auto-index

**优先级**：12 | **风险**：high

**目标**：添加带轮询 fallback 的文件变更监听器，为章节/总纲/细纲触发增量索引更新。

**步骤**：
1. 实现跨平台文件监听（带 fallback 轮询）
2. 每个变更文件触发增量索引更新
3. 将监听事件记录到 `watch-events.jsonl`

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py codex index watch --project-root <PROJECT_ROOT> --duration 30
```
**验收检查**：文件变更自动触发增量索引；`watch-events.jsonl` 记录每个事件；变更到可检索延迟证据已捕获

---

### T013 · M2 fast lookup by chapter number and scene tag

**优先级**：13 | **风险**：medium

**目标**：从增量索引数据中提供基于章节号和场景标签的确定性快速定位能力。

**步骤**：
1. 实现章节号查找路径
2. 实现场景标签查找路径
3. 两种查找均返回稳定的机器可读输出

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py codex index query --project-root <PROJECT_ROOT> --chapter 12
python -X utf8 webnovel-writer/scripts/webnovel.py codex index query --project-root <PROJECT_ROOT> --scene-tag confrontation
```
**验收检查**：章节查找返回预期目标；场景标签查找返回预期目标；输出格式对自动化稳定

---

## M3：会话 Skill + RAG 13档（T014–T016）

### T014 · M3 session-scoped skill profile loader

**优先级**：14 | **风险**：critical

**目标**：仅将选定的 skill profile 加载到会话本地目录，session stop 时清理，不触碰全局 Codex 路径。

**步骤**：
1. 添加 battle/description/consistency profile 模板
2. 将 profiles 加载到 `.webnovel/codex/sessions/<session_id>/skills`
3. 强制全局 skill 路径禁写保护，stop 时清理

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py codex session start --profile consistency --project-root <PROJECT_ROOT>
python -X utf8 webnovel-writer/scripts/webnovel.py codex session stop --session-id <SESSION_ID> --project-root <PROJECT_ROOT>
```
**验收检查**：会话本地 skill 目录使用选定 profile 创建；全局 Codex skill 路径保持不变；session stop 移除会话本地 skill 产物

---

### T015 · M3 implement codex rag verify metrics command

**优先级**：15 | **风险**：critical

**目标**：实现 `webnovel codex rag verify`，包含连通性、正确性、性能三层指标的 JSON 报告与阈值通过/失败判定。

**RAG 验收标准（13档）**：
- 连通性：vectors.db/index.db 可打开，rag_schema_meta 版本合法，最小检索可执行
- 正确性：60条查询基准集，Hit@5 >= 0.90，MRR@10 >= 0.70，章节约束正确率 >= 0.98
- 性能：检索 p95 <= 700ms，p99 <= 1200ms；增量索引 p95 <= 1500ms；可见延迟 p95 <= 3s

**步骤**：
1. 实现连通性检查
2. 实现正确性指标：Hit@5、MRR@10、章节约束准确率
3. 实现性能指标：检索 p95/p99、增量索引 p95、可见延迟 p95

**验收命令**：
```
python -X utf8 webnovel-writer/scripts/webnovel.py codex rag verify --project-root <PROJECT_ROOT> --report json
```
**验收检查**：JSON 报告包含所有必需指标；阈值违反产生非零退出码；通过摘要机器可读

---

### T016 · M3 CI gate and final acceptance package

**优先级**：16 | **风险**：high

**目标**：将 rag verify 集成到 CI 作为阻断门，更新 README/文档/操作手册以匹配实现行为和迁移路径。

**步骤**：
1. 将 rag verify 接入 CI workflow 为必需 job
2. 更新只读 dashboard 和 codex 统一工作流文档
3. 运行完整验收回归并记录证据

**验收命令**：
```
cd webnovel-writer && pytest
cd webnovel-writer/dashboard/frontend && npm run build
python -X utf8 webnovel-writer/scripts/webnovel.py codex rag verify --project-root <PROJECT_ROOT> --report json
```
**验收检查**：rag verify 失败时 CI 失败；文档反映实际命令和端点删除；所有任务 `passes=true` 后方可发布

---

## 启动 Harness

### 前提：设置 API Key

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
```

### 方式 A：Sisyphus 并行分发器（推荐，多 worktree 并行）

```powershell
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 `
  -RepoRoot d:\code\webnovel-writer `
  -MaxDispatches 16 `
  -MaxParallel 2 `
  -ApiKey $env:OPENAI_API_KEY
```

### 方式 B：Ralph 单线程循环（简单稳定）

```powershell
powershell -ExecutionPolicy Bypass -File running/ralph-loop.ps1 `
  -MaxIterations 16 `
  -ApiKey $env:OPENAI_API_KEY
```

### 干运行预检（查看队列顺序，不执行）

```powershell
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 -DryRun -MaxDispatches 16
```
