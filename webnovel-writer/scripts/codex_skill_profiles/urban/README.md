# Urban Skill Profile — 都市异能

> **Profile ID**: `urban`  
> **适用题材**: 都市异能、现代修真、隐世高手、都市系统流等以现代背景为舞台的网文  
> **Genre Profiles 参考**: `genre-profiles.md` §2.6 urban-power

## 概述

Urban Profile 为都市异能题材提供专项写作辅助。都市异能的核心魅力在于"现实与超凡的碰撞"——西装革履的上班族可能暗地里是S级异能者，外卖小哥或许是隐世宗门传人。

本 profile 聚焦都市异能的六大核心要素：

1. **身份隐藏** — 异能者的隐匿生存与"掉马"节奏
2. **现实锚定** — 社会结构、经济体系、行业逻辑的合理性
3. **三章一峰** — 紧凑的起承转合节奏
4. **装逼打脸** — 核心爽点模式的多样化
5. **产业链博弈** — 涉及行业的基本常识
6. **异能代价** — 能力使用的限制与冷却

## 文件结构

```
urban/
├── README.md           # 本文件：Profile 概述与使用说明
├── rules.md            # 都市异能专项写作规则（6 条核心约束）
└── check-weights.yaml  # Checker 权重覆盖配置（基于 genre-profiles §2.6）
```

## 加载规则

- **会话级加载**: 通过 `codex session start --profile urban` 启动时加载
- **推荐叠加**: `--profile urban,battle` (战斗场景) 或 `--profile urban,consistency` (身份逻辑校验)
- **Genre 配置联动**: 本 profile 的 checker 权重与 `genre-profiles.md` §2.6 urban-power 配置对齐

## Checker 权重说明

| Checker | 权重 | 说明 |
|---------|------|------|
| pacing | 1.0 | stagnation_threshold=3（都市文节奏偏快） |
| coolpoint | 1.0 | combo_interval=3（爽点间隔短，高密度） |
| consistency | 1.0 | 现实背景对一致性要求更高 |
| hook | 1.0 | 标准权重 |

## 题材特点速查

- 装逼打脸系列是核心爽点，但需多样化
- 身份隐藏→掉马的节奏控制是关键
- 社会地位变化是重要微兑现
- 感情线权重高（断档容忍度降至 8 章）
- 3 章一峰节奏：困境→初展→小胜+新阻力
