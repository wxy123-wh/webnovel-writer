# Romance Skill Profile — 言情/甜宠

> **Profile ID**: `romance`  
> **适用题材**: 言情、甜宠、都市恋爱、古代言情、校园恋爱等以感情线为核心的网文  
> **Genre Profiles 参考**: `genre-profiles.md` §2.3 romance

## 概述

Romance Profile 为言情/甜宠题材提供专项写作辅助。言情文的核心是"心动"——让读者为角色之间的每一次眼神交汇、每一次不经意的触碰而心跳加速。

本 profile 聚焦言情的七大核心要素：

1. **感情线核心** — 感情进展是绝对主线
2. **心动瞬间** — 每章至少 1 个心动场景
3. **甜虐节奏** — 7:3 的黄金比例
4. **身份差张力** — 利用差距制造矛盾
5. **吃醋桥段** — 适度使用关系升温手段
6. **表白时机** — 在最佳节点亮明心意
7. **关系进展标记** — 每阶段需有明确事件

## 文件结构

```
romance/
├── README.md           # 本文件：Profile 概述与使用说明
├── rules.md            # 言情/甜宠专项写作规则（7 条核心约束）
└── check-weights.yaml  # Checker 权重覆盖配置（基于 genre-profiles §2.3）
```

## 加载规则

- **会话级加载**: 通过 `codex session start --profile romance` 启动时加载
- **推荐叠加**: `--profile romance,description` (心动场景描写) 或 `--profile romance,consistency` (感情线逻辑校验)
- **Genre 配置联动**: 本 profile 的 checker 权重与 `genre-profiles.md` §2.3 romance 配置对齐

## Checker 权重说明

| Checker | 权重 | 说明 |
|---------|------|------|
| pacing | 1.0 | 感情线断档容忍度极低（fire_gap_max=5） |
| coolpoint | 1.0 | 心动瞬间本身就是微爽点，density=medium |
| consistency | 1.0 | 感情逻辑需要一致（不能忽冷忽热无理由） |
| hook | 1.0 | 标准权重 |

## 题材特点速查

- 感情线是绝对核心，断档容忍度极低
- 情绪钩是王牌（心疼/心动/吃醋）
- 关系进展是最重要的微兑现
- 甜虐比 7:3，虐后必有糖
- 每个关系阶段需有明确的标志性事件
