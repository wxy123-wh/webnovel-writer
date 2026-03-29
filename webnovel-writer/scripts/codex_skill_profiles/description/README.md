# Description Skill Profile — 描写场景辅助

> **Profile ID**: `description`  
> **适用场景**: 环境描写、人物出场、氛围营造、感官体验等非战斗描写密集型章节

## 概述

Description Profile 为场景描写、人物塑造、氛围营造提供专项写作辅助。优秀的描写是网文"沉浸感"的基石——它让读者"看到"而非"被告知"。

本 profile 通过以下机制保障描写质量：

1. **五感法则** — 超越纯视觉，调动多重感官体验
2. **人物出场规范** — 重要角色首次登场需有完整烙印
3. **环境服务原则** — 环境描写必须为叙事目标服务
4. **比喻节制** — 避免辞藻堆砌和俗套比喻
5. **留白艺术** — 关键场景不写满，留给读者参与
6. **信息分散释放** — 设定信息不一次性倾泻

## 文件结构

```
description/
├── README.md           # 本文件：Profile 概述与使用说明
├── rules.md            # 描写场景专项写作规则（6 条核心约束）
└── check-weights.yaml  # Checker 权重覆盖配置
```

## 加载规则

本 profile 中的 `rules.md` 会在以下时机被加载：

- **会话级加载**: 通过 `codex session start --profile description` 启动时，profile 文件被软链接到 `.webnovel/codex/sessions/<session_id>/skills/description/`
- **混合加载**: 可与其他 profile 同时激活（如 `--profile description,romance`），规则叠加执行
- **Checker 权重**: `check-weights.yaml` 在 Checker 执行阶段覆盖默认权重

## Checker 权重说明

| Checker | 默认权重 | 本 Profile 权重 | 说明 |
|---------|---------|----------------|------|
| pacing | 1.0 | **0.8** | 描写章节节奏容忍度更高，允许铺垫 |
| coolpoint | 1.0 | **0.7** | 纯描写章节爽点密度要求降低 |
| consistency | 1.0 | **1.0** | 一致性保持标准 |
| hook | 1.0 | **0.9** | 描写章末钩子可适度弱化 |

## 适用场景

本 profile 适用于以下场景类型：

- 新环境首次登场（城市/宗门/秘境）
- 重要角色首次出场
- 氛围转换（紧张→安宁、明亮→阴暗）
- 情感高潮前的铺垫
- 战前/战后的对比描写

可与其他 profile 叠加使用，为战斗/恋爱/悬疑等场景提供描写层辅助。
