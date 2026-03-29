# Xianxia Skill Profile — 修仙/玄幻

> **Profile ID**: `xianxia`  
> **适用题材**: 修仙、玄幻、仙侠等以修炼体系和境界突破为核心的网文类型  
> **Genre Profiles 参考**: `genre-profiles.md` §2.2 xianxia

## 概述

Xianxia Profile 为修仙/玄幻题材提供完整的写作辅助框架。修仙文是网文中生命力最持久的题材之一，其核心吸引力在于"逆天改命"的成长叙事和宏大世界观。

本 profile 聚焦修仙文的七大核心要素：

1. **境界体系** — 成长刻度的可视化设计
2. **资源货币化** — 灵石/丹药/功法驱动的微兑现系统
3. **逆天改命** — 主角突破常规的合理化机制
4. **宗门结构** — 正邪对立中的灰色地带
5. **天道法则** — 高阶约束与战力天花板
6. **机缘设计** — 四步走机缘获取模式
7. **修炼过程** — 不可跳过的感悟描写

## 文件结构

```
xianxia/
├── README.md           # 本文件：Profile 概述与使用说明
├── rules.md            # 修仙/玄幻专项写作规则（7 条核心约束）
└── check-weights.yaml  # Checker 权重覆盖配置（基于 genre-profiles §2.2）
```

## 加载规则

- **会话级加载**: 通过 `codex session start --profile xianxia` 启动时加载
- **推荐叠加**: `--profile xianxia,battle` (战斗场景) 或 `--profile xianxia,consistency` (设定校验)
- **Genre 配置联动**: 本 profile 的 checker 权重与 `genre-profiles.md` §2.2 xianxia 配置对齐

## Checker 权重说明

| Checker | 权重 | 说明 |
|---------|------|------|
| pacing | 1.0 | stagnation_threshold=4（修仙文允许更多铺垫） |
| coolpoint | 1.0 | combo_interval=5（爽点节奏适中） |
| consistency | 1.1 | 境界体系对一致性要求更高 |
| hook | 1.0 | 标准权重 |

## 题材特点速查

- 需要世界观构建，允许更多铺垫章
- 境界突破是核心期待，建议 8-10 级可视化体系
- 资源货币化体系（灵石/丹药/功法）是核心微兑现载体
- 设定约束可作为合理 Override 理由（WORLD_RULE_CONSTRAINT）
- 债务倍率 0.9（相对宽松，允许更长线的伏笔布局）
