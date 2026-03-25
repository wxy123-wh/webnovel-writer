# 文档中心

本目录承载 `README.md` 之外的详细说明，按模块拆分：

- [架构与模块](#架构与模块)
- [命令详解](#命令详解)
- [RAG 与配置](#rag-与配置)
- [题材模板](#题材模板)
- [运维与恢复](#运维与恢复)
- [Codex 使用](#codex-使用)
- [需求与实施](#需求与实施)

## 架构与模块

- `architecture.md`：系统架构、核心理念、双 Agent、六维审查

## 命令详解

- `commands.md`：`/webnovel-*` 命令详细说明

## RAG 与配置

- `rag-and-config.md`：RAG 检索与环境配置

## 题材模板

- `genres.md`：题材模板与复合题材规则

## 运维与恢复

- `operations.md`：项目结构与故障恢复/运维手册

## Codex 使用

- `codex.md`：Codex 本地仓库模式下的初始化、指针绑定与常用 CLI

## 需求与实施

- `srs-codex-exclusive-rebuild.md`：Codex 专属改造与双纲协作工作台需求规格说明书（SRS）
- `codex-exclusive-implementation-plan.md`：基于 SRS 的实施计划与里程碑任务分解
- `openspec-execution-plan.md`：面向 Codex 子代理并行执行的 OpenSpec 规范执行计划（模块/接口/技术/验收）

建议阅读顺序：

1. 先看 `../README.md`（安装与上手）
2. 再看 `srs-codex-exclusive-rebuild.md`（确认目标需求）
3. 再看 `codex-exclusive-implementation-plan.md`（按任务推进）
4. 最后按需查阅架构、命令和运维文档
