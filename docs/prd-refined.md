# PRD Refined（Phase 1 收敛冻结稿）

> 日期：2026-03-31
> 目标：把项目从多入口叙事收敛为唯一主产品形态

## 1. 产品定义

Webnovel Writer 的唯一主产品形态定义为：**对话式 Chat Agent 写作台**。

用户通过对话驱动创作；Skill 库支持按会话装载；内部固定保持“大纲 → 剧情 → 事件 → 场景 → 整章整合”的流水线；RAG 索引与验证负责长篇一致性保障。

## 2. 冻结决策

1. **主入口唯一化**：主入口固定为 Chat Agent / Chat UI。
2. **CLI 降级**：CLI 保留，但固定为自动化、运维、脚本 companion。
3. **Dashboard 降级**：Dashboard 固定为只读观察与诊断面。
4. **VS Code 降级**：VS Code 插件固定为只读 companion。
5. **历史心智退出主线**：不再把 Codex / ClaudeCode / 多插件形态作为主产品定义。
6. **Pipeline 固定保留**：继续保持大纲 → 剧情 → 事件 → 场景 → 整章整合。
7. **Skill 保留并升级定位**：Skill 成为主产品核心能力，不再只是附属 profile。
8. **RAG 保留并升级定位**：RAG 作为一致性底座保留，不再被视为独立产品面。

## 3. Phase 1 范围

### 3.1 In Scope

1. 统一 README、架构文档、接口文档、模块文档的主产品叙事。
2. 明确 core / apps 的目标模型。
3. 明确各入口的角色边界。
4. 冻结后续重构方向，避免再新增并列主入口。

### 3.2 Out of Scope

1. 不在本阶段完成完整代码搬迁。
2. 不在本阶段承诺交付完整新 Chat UI。
3. 不在本阶段新增新的产品入口或管理后台。
4. 不在本阶段扩展新的写作流程。

## 4. 功能与架构要求

### FR-1 主入口唯一化

1. 所有高可见文档必须明确：主产品形态只有 Chat Agent / Chat UI。
2. 不再把 CLI、Dashboard、VS Code 插件写成并列主入口。

### FR-2 Companion / Ops Surface 固定化

1. CLI 的职责固定为自动化、运维、脚本调用。
2. Dashboard 的职责固定为只读观察与诊断。
3. VS Code 插件的职责固定为只读 companion。

### FR-3 核心能力内核化

目标模型必须固定包含：

1. `agent_runtime`
2. `skill_system`
3. `pipeline`
4. `rag_index`
5. `project_state`

### FR-4 写作流程固定化

写作流程继续保持：

1. 大纲
2. 剧情
3. 事件
4. 场景
5. 整章整合

### FR-5 一致性保障保留

1. 保留当前索引、检索、验证链路。
2. 保留会话级 skill 装载能力。
3. 保留 RAG 验证作为底层质量保障手段。

## 5. 验收标准

Phase 1 完成的二元标准如下：

1. README 第一屏已把 Chat Agent / Chat UI 定义为唯一主入口。
2. 架构文档已改为 core / apps 目标模型。
3. 接口与模块文档已把 CLI / Dashboard / VS Code 降级为 companion / ops surface。
4. 不再有高可见文档把 Codex / CLI / Dashboard / VS Code 写成并列主产品入口。

## 6. 后续阶段说明

Phase 1 完成后，后续阶段才允许继续推进：

1. core 能力抽离
2. chat-ui 实现
3. 旧入口对 core 的统一适配

在此之前，不允许再扩展新的并列主入口。
