# OpenSpec 规范执行计划（基于 SRS v1.1）

## 0. 文档元信息

| 项 | 内容 |
|---|---|
| Plan ID | OSP-WNW-CODEX-20260325-01 |
| 版本 | v1.0 |
| 基线输入 | `docs/srs-codex-exclusive-rebuild.md`（v1.1，2026-03-25） |
| 适用仓库 | `D:\code\webnovel-writer` |
| 执行模式 | Codex 多子代理并行开发（Lead + Worker） |
| 目标 | 将 SRS 的 FR/BR/AC 转化为可并行执行、可验收、可追踪的工程任务 |

## 1. OpenSpec 执行范围与原则

### 1.1 范围映射

| SRS 模块 | OpenSpec 工作流模块 | 覆盖需求 |
|---|---|---|
| A Codex 专属化改造 | M-A Runtime & Migration | FR-MIG-001~005 |
| B 工作区专属 Skill 库 | M-B Workspace Skills | FR-SKL-001~006 |
| C 设定集页签与设定词典 | M-C Settings & Dictionary | FR-SET-001~006 |
| D 双纲同屏与右键拆分 | M-D Dual Outline & Split | FR-OUT-001~006 |
| E 场景化细纲与重拆回退 | M-E Scene Segment & Resplit | FR-SCN-001~006 |
| F 全局文本右键协助修改 | M-F Global Edit Assist | FR-EDIT-001~005 |
| G 文档同步 | M-G Docs Alignment | FR-DOC-001~005 |

### 1.2 并行执行原则（给 Codex 子代理）

1. 先做“骨架拆分”，再并行做“模块填充”：先拆后端路由与前端页面骨架，避免多人改同一文件冲突。
2. 每个子代理只拥有一个文件域（Path Ownership），禁止跨域改动。
3. 接口先行：后端先提交 OpenAPI/请求响应模型，再由前端对接。
4. 所有任务均绑定验收用例（自动化优先，手工兜底）。
5. 所有写入动作必须遵循工作区隔离与原子落盘。

## 2. 技术基线与新增技术

### 2.1 后端技术

| 领域 | 技术 |
|---|---|
| Web API | FastAPI (`webnovel-writer/dashboard`) |
| 数据模型 | Pydantic v2（请求/响应/持久化 schema） |
| 存储 | SQLite（结构化索引）+ JSON/JSONL（流程与日志） |
| 并发安全 | `filelock` + `security_utils.atomic_write_json` |
| 文件安全 | `path_guard.safe_resolve`（防路径穿越） |
| 事件通知 | SSE（沿用 `/api/events`） |

### 2.2 前端技术

| 领域 | 技术 |
|---|---|
| UI 框架 | React 19 + Vite 6 |
| 网络层 | `fetch` + 统一 API client |
| 交互 | 原生右键菜单事件 + 自定义 Context Menu 组件 |
| 状态管理 | React Hooks（不引入重量级状态库） |

### 2.3 测试与质量

| 层级 | 技术 |
|---|---|
| 后端单元/集成 | `pytest` + FastAPI TestClient |
| 前端组件 | `vitest` + `@testing-library/react`（新增） |
| 端到端 | Playwright（新增，覆盖右键交互主链路） |
| 静态检查 | Python `ruff`（可选）+ 前端 `eslint`（可选） |

## 3. 模块级设计（接口 + 数据 + 技术）

## M-A Runtime & Migration（Codex 专属化）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| CLI | `webnovel migrate codex --project-root <path> [--dry-run]` | 一次性迁移 `.claude` 兼容痕迹，生成迁移报告 |
| API | `GET /api/runtime/profile` | 返回当前工作区运行时配置与兼容状态 |
| API | `POST /api/runtime/migrate` | 触发迁移（仅本工作区） |

### 数据规范

1. `.webnovel/migrations/codex-migrate-<timestamp>.json`：迁移明细。
2. 迁移报告最小字段：`moved, removed, skipped, warnings, created_at`。

### 核心技术

1. 基于 `project_locator.py` 收敛为 `.codex` 优先路径。
2. 历史 `.claude` 信息只读迁移，不再作为运行时主路径。
3. 迁移过程全量 dry-run 支持，避免误操作。

### 模块验收

1. AC-001 通过：运行链路无 Claude 依赖。
2. `--dry-run` 与实际执行输出差异可解释且可追踪。

## M-B Workspace Skills（工作区 Skill 库）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| CLI | `webnovel skill list` | 列出技能及状态 |
| CLI | `webnovel skill add --id --name --desc --from <path>` | 新增技能 |
| CLI | `webnovel skill enable --id` / `disable --id` | 启停技能 |
| CLI | `webnovel skill remove --id` | 删除技能 |
| API | `GET /api/skills` | 列表查询（支持 `enabled` 过滤） |
| API | `POST /api/skills` | 新建技能 |
| API | `PATCH /api/skills/{skill_id}` | 更新技能元信息 |
| API | `POST /api/skills/{skill_id}/enable` | 启用 |
| API | `POST /api/skills/{skill_id}/disable` | 禁用 |
| API | `DELETE /api/skills/{skill_id}` | 删除 |
| API | `GET /api/skills/audit` | 审计日志查询 |

### 数据规范

1. `.webnovel/skills/registry.json`：`id, name, enabled, scope, updated_at, last_called_at`。
2. `.webnovel/skills/<skill-id>/SKILL.md` + `meta.json`。
3. `.webnovel/logs/skill-audit.jsonl`：操作审计。

### 核心技术

1. Pydantic 校验 Skill meta。
2. 文件锁保护并发编辑 registry。
3. 调用链过滤器强制 `workspace + enabled=true`。

### 模块验收

1. AC-002 通过：A/B 工作区技能严格隔离。
2. 禁用技能不参与调用（日志中不可见调用记录）。

## M-C Settings & Dictionary（设定集与词典抽离）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| API | `GET /api/settings/files/tree` | 获取设定集文件树 |
| API | `GET /api/settings/files/read?path=` | 读取设定集文件 |
| API | `POST /api/settings/dictionary/extract` | 抽离词典（全量/增量） |
| API | `GET /api/settings/dictionary` | 查询词典条目 |
| API | `POST /api/settings/dictionary/conflicts/{id}/resolve` | 冲突处理 |
| CLI | `webnovel setting extract-dictionary [--incremental]` | CLI 触发抽离 |

### 数据规范

1. `.webnovel/dictionaries/setting-dictionary.json`。
2. 条目最小字段：`id, term, type, attrs, source_file, source_span, status, fingerprint`。
3. 冲突队列：`status=conflict`，仅人工确认后转 `confirmed`。

### 核心技术

1. 文本分块 + 指纹去重（增量抽离）。
2. 冲突检测器（同 term/type 不同 attrs）。
3. 来源定位：保存文件相对路径 + 字符区间。

### 模块验收

1. AC-009 通过：条目可追溯到源文件位置。
2. 重复抽离不产生重复条目（指纹去重命中率可验证）。

## M-D Dual Outline & Split（双纲同屏与拆分）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| API | `GET /api/outlines` | 读取总纲/细纲内容及映射 |
| API | `POST /api/outlines/split/preview` | 拆分预览（不落盘） |
| API | `POST /api/outlines/split/apply` | 拆分落盘（记录锚点） |
| API | `GET /api/outlines/splits` | 查询拆分历史与锚点 |
| 前端事件 | `outline.selection.changed` | 记录选区 |
| 前端事件 | `outline.split.requested` | 触发右键拆分 |

### 数据规范

1. `.webnovel/outlines/split-map.json`：锚点与片段映射。
2. `.webnovel/outlines/detailed-segments.jsonl`：场景片段流水。
3. `大纲/细纲.md`：按 `order_index` 生成展示。

### 核心技术

1. 选区偏移归一化（字符级 offset + 段落索引双锚点）。
2. 拆分服务输出“无修饰扩写”后再经过规则校验器。
3. 原子落盘：先写临时文件，再 replace。

### 模块验收

1. AC-003、AC-004、AC-005、AC-006 通过。
2. 选区 1k-2k 字拆分建议耗时 <= 10s（NFR-002）。

## M-E Scene Segment & Resplit（重拆回退）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| API | `POST /api/outlines/resplit/preview` | 根据新选区计算回退范围 |
| API | `POST /api/outlines/resplit/apply` | 回退后重拆并重排 |
| API | `POST /api/outlines/order/validate` | 落盘前顺序校验 |
| CLI | `webnovel outline resplit --start --end` | CLI 重拆入口 |

### 数据规范

1. 回退记录追加到 `split-map.json.history[]`。
2. 重拆条目必须包含 `rollback_strategy`：`smaller_selection` / `larger_selection`。

### 核心技术

1. 区间重叠计算（按 source_start/source_end）。
2. 顺序冲突阻断写入（BR-SCN-004）。
3. 幂等重试：失败不污染既有细纲顺序。

### 模块验收

1. AC-007 通过：选区更小/更大均按规则回退。
2. 冲突时必须阻断并提示，不得写坏细纲。

## M-F Global Edit Assist（全局右键协助修改）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| API | `POST /api/edit-assist/preview` | 仅对选区生成建议 |
| API | `POST /api/edit-assist/apply` | 用户确认后应用修改 |
| API | `GET /api/edit-assist/logs` | 查询修改日志 |
| 前端事件 | `editor.contextmenu.assist` | 全编辑区统一右键入口 |

### 数据规范

1. `.webnovel/edits/assist-log.jsonl`。
2. 最小字段：`id, file_path, selection_start, selection_end, prompt, preview, applied, created_at`。

### 核心技术

1. 最小修改范围保护：默认只提交选中文本。
2. 双阶段提交：Preview -> Confirm Apply。
3. 失败回滚：应用失败保留原文并记录原因。

### 模块验收

1. AC-008 通过：任意编辑区右键可唤起协助。
2. 未确认前不落盘（FR-EDIT-004）。

## M-G Docs Alignment（文档同步）

### 接口规范

| 类型 | 接口 | 说明 |
|---|---|---|
| 文档产物 | `README.md` + `docs/*.md` | 统一 Codex 叙事与命令 |
| 校验命令 | `webnovel preflight --format json` | 文档命令可执行性抽查 |

### 模块验收

1. AC-010 通过：文档评审通过，无过时 Claude 路径说明。

## 4. 子代理并行执行计划（可直接排程）

## 4.1 并行波次

| 波次 | 目标 | 任务包 |
|---|---|---|
| W0 | 架构拆分与接口冻结 | T00 |
| W1 | 基础骨架并行 | T01, T02, T03 |
| W2 | 核心后端能力并行 | T04, T05, T06, T07 |
| W3 | 前端对接与规则补齐 | T08, T09, T10 |
| W4 | 测试与验收 | T11 |
| W5 | 文档收口与发布 | T12 |

## 4.2 任务包明细（子代理级）

| 任务ID | 建议子代理 | 模块 | 依赖 | 主要文件域（独占） | 关键接口 | 交付物 | 完成判定 |
|---|---|---|---|---|---|---|---|
| T00 | `lead-arch` | 共性 | 无 | `dashboard/app.py`, `dashboard/routers/*`, `dashboard/services/*`, `dashboard/frontend/src/pages/*` | 路由前缀与请求模型冻结 | 接口清单 + 文件 ownership 文档 | 评审通过后才允许 W1 开始 |
| T01 | `worker-runtime` | M-A | T00 | `scripts/project_locator.py`, `scripts/data_modules/webnovel.py`, `scripts/migrations/*` | `webnovel migrate codex` | 迁移命令+报告 | AC-001 自动化通过 |
| T02 | `worker-backend-core` | 共性 | T00 | `dashboard/app.py`, `dashboard/routers/__init__.py`, `dashboard/models/*` | 新增写接口路由注册 | API 骨架可运行 | `/docs` 可见新路由 |
| T03 | `worker-frontend-core` | 共性 | T00 | `dashboard/frontend/src/App.jsx`, `src/pages/*`, `src/components/*` | 页面路由与通用右键框架 | 双纲/设定/技能页面骨架 | 页面可切换，无报错 |
| T04 | `worker-skill-be` | M-B | T02 | `dashboard/routers/skills.py`, `dashboard/services/skills/*`, `scripts/data_modules/skill_manager.py` | Skill CRUD API/CLI | registry + 审计日志 | AC-002 用例通过 |
| T05 | `worker-setting-be` | M-C | T02 | `dashboard/routers/settings.py`, `dashboard/services/dictionary/*` | 词典抽离/冲突 API | setting-dictionary 落盘 | AC-009 用例通过 |
| T06 | `worker-split-be` | M-D | T02 | `dashboard/routers/outlines.py`, `dashboard/services/split/*` | split preview/apply | 锚点+细纲落盘 | AC-004~006 通过 |
| T07 | `worker-assist-be` | M-F | T02 | `dashboard/routers/edit_assist.py`, `dashboard/services/edit_assist/*` | assist preview/apply | 协助修改日志 | AC-008 后端侧通过 |
| T08 | `worker-skill-fe` | M-B | T03,T04 | `dashboard/frontend/src/pages/SkillsPage.jsx`, `src/api/skills.js` | Skill 管理 UI | 列表/启停/新增交互 | 手工验收 + 组件测试通过 |
| T09 | `worker-setting-outline-fe` | M-C/M-D | T03,T05,T06 | `dashboard/frontend/src/pages/SettingsPage.jsx`, `OutlineWorkspacePage.jsx`, `src/api/settings.js`, `src/api/outlines.js` | 设定词典 + 右键拆分 UI | 双栏同屏 + 抽离按钮 | AC-003~005 前端侧通过 |
| T10 | `worker-resplit-fe-be` | M-E | T06,T09 | `dashboard/services/split/resplit.py`, `dashboard/frontend/src/components/ResplitDialog.jsx` | resplit preview/apply | 回退策略可视化与落盘 | AC-007 通过 |
| T11 | `worker-qa` | 验收 | T01~T10 | `scripts/tests/*`, `dashboard/tests/*`, `dashboard/frontend/tests/*` | API/UI/E2E 全链路 | 自动化报告 + 缺陷清单 | 全部 AC 用例通过 |
| T12 | `worker-docs` | M-G | T11 | `README.md`, `docs/*.md` | 命令与流程文档同步 | 发布文档包 | AC-010 评审通过 |

## 4.3 子代理执行提示模板（建议）

1. 输入固定包含：`任务ID + 独占文件域 + 接口契约 + 验收用例`。
2. 强制要求：不得改动其他代理文件域，若必须改动先提交接口变更申请。
3. 每个子代理提交内容必须包含：`变更文件列表 + 测试结果 + 未决风险`。

## 5. 验收规范（最终 Gate）

## 5.1 SRS 验收项映射

| AC 编号 | 验收动作 | 自动化/人工 | 通过标准 |
|---|---|---|---|
| AC-001 | 搜索运行路径与文档中的 Claude 主链路依赖 | 自动化 + 人工审阅 | 无运行时依赖；迁移说明完整 |
| AC-002 | A/B 工作区各新增一个同名 Skill 并互查 | 自动化 | 互不可见，启停状态独立 |
| AC-003 | Dashboard 打开双纲页面 | 人工 + E2E | 同屏并排显示总纲/细纲 |
| AC-004 | 选中总纲文本右键拆分到细纲 | E2E | 细纲新增场景片段 |
| AC-005 | 检查拆分文本风格约束 | 自动化规则校验 + 人工抽查 | 无修辞、按段存储 |
| AC-006 | 检查锚点与 `order_index` 顺序 | 自动化 | 顺序一致且可回溯 |
| AC-007 | 小选区/大选区分别重拆 | E2E + 自动化 | 回退策略与 SRS 一致 |
| AC-008 | 设定/大纲/正文编辑区右键协助修改 | E2E | 均可唤起，预览后应用 |
| AC-009 | 从设定集抽离并处理冲突条目 | 自动化 + 人工 | 条目结构正确，冲突可确认 |
| AC-010 | 文档全量评审 | 人工 | Codex 专属叙事一致 |

## 5.2 接口验收

1. 写接口必须返回标准错误码：`400/403/404/409/500`，并包含 `error_code`。
2. 所有写接口必须带工作区隔离校验，跨工作区请求返回 `403`。
3. `split/apply` 与 `resplit/apply` 必须具备幂等保护（重复提交不乱序）。
4. `edit-assist/apply` 必须校验选区版本（防止并发编辑覆盖）。

## 5.3 非功能验收

1. 性能：1k-2k 字拆分接口 p95 <= 10s。
2. 可靠性：注入失败后可重试，细纲顺序不破坏。
3. 可观测：Skill/Split/Resplit/Edit 均有 JSONL 审计日志。
4. 安全：路径穿越、跨工作区写入、非法选区均被拦截。

## 5.4 发布 DoD（Definition of Done）

1. SRS 的 FR/BR/AC 全部有“实现映射 + 测试映射”。
2. W0~W5 任务均有完成记录与产物链接。
3. 自动化测试通过且无 P0/P1 缺陷未关闭。
4. 文档、命令、接口版本一致。

## 6. 风险与并行冲突控制

1. 冲突风险：多人修改 `dashboard/app.py`。规避：W0 先路由拆分，后续只改各自 router 文件。
2. 数据一致性风险：拆分与重拆并发写细纲。规避：文件锁 + 顺序校验 + 乐观版本号。
3. 交互一致性风险：不同文本区右键行为不一致。规避：统一 Context Menu 组件协议。
4. 进度风险：前端等后端接口。规避：先冻结 API schema，前端使用 mock 并行。

## 7. 建议里程碑（日期可调整）

| 里程碑 | 目标 | 建议时长 |
|---|---|---|
| M1 | W0+W1 完成（骨架 + 迁移） | 3-4 天 |
| M2 | W2 完成（核心后端） | 4-5 天 |
| M3 | W3 完成（前端集成 + 重拆） | 4-5 天 |
| M4 | W4+W5 完成（验收 + 文档发布） | 3 天 |

