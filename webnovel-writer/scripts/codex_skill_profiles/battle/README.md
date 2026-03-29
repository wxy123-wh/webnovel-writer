# Battle Skill Profile — 战斗场景辅助

> **Profile ID**: `battle`  
> **适用场景**: 战斗、对决、大规模战役、武技/异能对抗等动作密集型章节

## 概述

Battle Profile 为战斗场景提供专项写作辅助。战斗是网文中最核心的爽点载体之一，但也是最容易出现"流水账"、"节奏失控"、"爽感递减"等问题的场景类型。

本 profile 通过以下机制保障战斗场景质量：

1. **节奏控制规则** — 防止连续战斗导致的阅读疲劳
2. **力量对比建模** — 战前建立合理预期，战中方有悬念
3. **伤害累积追踪** — 确保战斗后果有持续性
4. **招式意外设计** — 每场战斗至少一个出人意料要素
5. **情绪线穿插** — 纯动作描写枯燥，需融入内心/情感
6. **章末转折点** — 维持追读欲望

## 文件结构

```
battle/
├── README.md           # 本文件：Profile 概述与使用说明
├── rules.md            # 战斗场景专项写作规则（7 条核心约束）
└── check-weights.yaml  # Checker 权重覆盖配置
```

## 加载规则

本 profile 中的 `rules.md` 会在以下时机被加载：

- **会话级加载**: 通过 `codex session start --profile battle` 启动时，profile 文件被软链接到 `.webnovel/codex/sessions/<session_id>/skills/battle/`
- **混合加载**: 可与其他 profile 同时激活（如 `--profile battle,xianxia`），规则叠加执行
- **Checker 权重**: `check-weights.yaml` 在 Checker 执行阶段覆盖默认权重

## Checker 权重说明

| Checker | 默认权重 | 本 Profile 权重 | 说明 |
|---------|---------|----------------|------|
| pacing | 1.0 | **1.3** | 战斗场景节奏更敏感，停滞阈值收紧至 2 章 |
| coolpoint | 1.0 | **1.5** | 战斗是爽点密集区，每章至少 2 个爽点 |
| consistency | 1.0 | **0.8** | 战斗中一致性检查适度放宽（允许招式创新） |
| hook | 1.0 | **1.2** | 战斗章末必须有转折或悬念 |

## 适用题材

本 profile 适用于所有包含战斗元素的题材，包括但不限于：

- 修仙/玄幻（xianxia）
- 都市异能（urban）
- 末世生存（apocalypse）
- 爽文/系统流（shuangwen）
- 电竞（esports）

可与其他 genre profile 叠加使用。
