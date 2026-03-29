# Mystery Skill Profile — 悬疑推理

> **Profile ID**: `mystery`  
> **适用题材**: 推理、悬疑、侦探、密室杀人、犯罪推理等以谜题驱动的网文  
> **Genre Profiles 参考**: `genre-profiles.md` §2.4 mystery

## 概述

Mystery Profile 为悬疑推理题材提供专项写作辅助。悬疑推理的核心在于"谜题的编织与拆解"——真相必须藏在暗处，但线索必须公平地呈现在读者面前。

本 profile 聚焦悬疑推理的七大核心要素：

1. **线索管理** — 明线/暗线/误导线的三层架构
2. **公平性原则** — 真相揭示时读者可回溯
3. **推理逻辑** — 每步推理必须有据可依
4. **反转设计** — 多层反转的节奏控制
5. **氛围营造** — 用环境暗示制造不安感
6. **嫌疑人管理** — 多线嫌疑人线索并行
7. **伏笔密度** — 高密度的有效伏笔

## 文件结构

```
mystery/
├── README.md           # 本文件：Profile 概述与使用说明
├── rules.md            # 悬疑推理专项写作规则（7 条核心约束）
└── check-weights.yaml  # Checker 权重覆盖配置（基于 genre-profiles §2.4）
```

## 加载规则

- **会话级加载**: 通过 `codex session start --profile mystery` 启动时加载
- **推荐叠加**: `--profile mystery,consistency` (线索逻辑校验) 或 `--profile mystery,description` (氛围营造)
- **Genre 配置联动**: 本 profile 的 checker 权重与 `genre-profiles.md` §2.4 mystery 配置对齐

## Checker 权重说明

| Checker | 权重 | 说明 |
|---------|------|------|
| pacing | 1.0 | stagnation_threshold=3（推理文不允许长期无进展） |
| coolpoint | 1.0 | combo_interval=10（爽点间隔长，推理高潮为主） |
| consistency | 1.2 | 推理文对一致性要求极高，逻辑必须自洽 |
| hook | 1.0 | 标准权重 |

## 题材特点速查

- 逻辑完整性优先于爽点密度
- 信息兑现是核心微兑现（持续线索推进）
- LOGIC_INTEGRITY 可作为降级钩子强度的合理理由
- 债务倍率 0.8（最宽松，允许长线伏笔布局）
- 爽点密度 low，但推理高潮的爽感更为集中和强烈
