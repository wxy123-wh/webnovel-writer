# Codex 使用说明

本项目已支持在 Codex 中直接使用统一 CLI，不依赖 Claude Marketplace 插件目录。

## 1) 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 2) 初始化小说项目

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py init ./webnovel-project "你的书名" "题材"
```

示例：

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py init ./凡人资本论 "凡人资本论" "都市脑洞+规则怪谈"
```

## 3) 绑定工作区（建议）

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py use "<PROJECT_ROOT>" --workspace-root "<WORKSPACE_ROOT>"
```

说明：
- 若工作区存在 `.codex/`，写入 `workspace/.codex/.webnovel-current-project`；
- 若仅存在 `.claude/`，自动回退写入 `.claude` 指针；
- 同时写入用户级 registry：`~/.codex/webnovel-writer/workspaces.json`（兼容 `~/.claude/...`）。

## 4) 预检

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<WORKSPACE_ROOT_OR_PROJECT_ROOT>" preflight
```

## 5) 常用命令

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py where
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<WORKSPACE_ROOT_OR_PROJECT_ROOT>" extract-context --chapter 1 --format text
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<WORKSPACE_ROOT_OR_PROJECT_ROOT>" status -- --focus all
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<WORKSPACE_ROOT_OR_PROJECT_ROOT>" index stats
```

## 6) Dashboard（可选）

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<WORKSPACE_ROOT_OR_PROJECT_ROOT>" dashboard
```

说明：
- 推荐通过统一 CLI 启动，避免手动 `cd` 与 `PYTHONPATH` 问题；
- 若 `.webnovel/index.db` 不存在，会自动执行一次轻量初始化（等价于 `index stats`）；
- 如不希望自动初始化，可追加 `--no-bootstrap-index`。

默认地址：`http://127.0.0.1:8765`
