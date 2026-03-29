# Running 目录命令手册

> 所有命令在项目根目录 `d:\code\webnovel-writer` 下执行

---

## 一键启动（推荐入口）

```powershell
# 打开 Windows Terminal 原生分屏面板（Dispatcher 前台直接可见 + 自动 Agent 分屏）
powershell -ExecutionPolicy Bypass -File running/open-dashboard.ps1 -ApiKey "sk-xxx"

# 只打开监控面板，不启动 dispatcher
powershell -ExecutionPolicy Bypass -File running/open-dashboard.ps1 -NoDispatcher

# 自定义并行数
powershell -ExecutionPolicy Bypass -File running/open-dashboard.ps1 -ApiKey "sk-xxx" -MaxParallel 3
```

### 窗口布局说明

```
┌────────────────────────────┬──────────────────┐
│                            │  Task Status     │
│   Dispatcher               │  (watch-status)  │
│   （前台直接输出，可看到    ├──────────────────┤
│    codex 的实时交互流）     │  Agent Monitor   │
│                            │  （监听 sessions/│
│                            │   自动分裂窗格） │
└────────────────────────────┴──────────────────┘
                                     │
                        每个新 Agent 自动在此追加:
                        ┌──────────────────────┐
                        │  ⚙ CODE T003         │
                        │  Get-Content -Wait   │
                        │  （原生 tail，实时流）│
                        └──────────────────────┘
```

### 仅启动 Agent 窗格监听器（已有 wt 窗口中运行）

```powershell
# 在任意 wt 窗格内运行，监听 sessions/ 并自动分裂 Agent 窗格
powershell -ExecutionPolicy Bypass -File running/open-agent-panes.ps1

# 自定义参数
powershell -ExecutionPolicy Bypass -File running/open-agent-panes.ps1 `
  -PollInterval 1 `
  -MaxPanes 6 `
  -TailLines 60
```

---

## 监控视图（单独运行）

```powershell
# ★ 推荐：类 Codex CLI 实时多 Agent 对话面板
#   - 上方：Dispatcher 日志（实时流式）
#   - 下方：每个子 Agent 独立面板，区分 thinking / tool / message
#   - 右侧：任务队列状态摘要
python running/watch-logs.py

# 自定义刷新间隔（秒，默认 1.5）
python running/watch-logs.py 1

# 任务状态单独查看（精简表格视图）
python running/watch-status.py
python running/watch-status.py 5
```

### watch-logs.py 面板说明

```
┌─────────────────────────────────────┬──────────────┐
│  Sisyphus Dispatcher                │  Task Queue  │
│  (dispatcher-out.txt 实时流)         │  T001 done   │
├──────────┬──────────┬───────────────│  T002 running│
│ ⚙ T003   │ ⚙ T004   │  ✔ T005 eval │  T003 pending│
│  ◦ 思考...│  ⚙ 工具  │  ▶ 回复...   │  ...         │
└──────────┴──────────┴───────────────┴──────────────┘

图例：
  ◦  thinking（模型推理）
  ⚙  tool call（工具调用）
  ←  tool result（工具返回）
  ▶  assistant message（最终回复）
  ✗  error
  ✓  PASS
```

> **前提**：`run-codex-stage.ps1` 已升级为实时流式写入，
> Agent 输出一边产生一边刷新到面板，无需等待进程退出。

---

## Dispatcher / 调度器

```powershell
# 启动 Sisyphus 并行调度（默认，推荐）
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -ApiKey "sk-xxx"

# 从环境变量读取 key
$env:OPENAI_API_KEY = "sk-xxx"
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1

# Ralph 单线程模式
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -Mode ralph -ApiKey "sk-xxx"

# 预览任务队列（不真正执行）
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -DryRun -ApiKey dummy

# 直接调用 dispatcher（完整参数，跳过 blocked 继续派发）
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 `
  -RepoRoot d:\code\webnovel-writer `
  -ApiKey "sk-xxx" `
  -ApiBaseUrl https://api.asxs.top/v1 `
  -MaxDispatches 16 `
  -MaxParallel 2 `
  -ContinueWhenBlocked
```

---

## 手动执行单个 Stage

```powershell
# 手动执行单个 coding / evaluator stage
powershell -ExecutionPolicy Bypass -File running/run-codex-stage.ps1 `
  -RepoRoot d:\code\webnovel-writer `
  -WorktreePath <worktree_path> `
  -CodexBin D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe `
  -PromptPath <prompt_file> `
  -OutputLastMessagePath <last_msg_file> `
  -TranscriptPath <transcript_file> `
  -ApiKey "sk-xxx" `
  -ApiBaseUrl https://api.asxs.top/v1

# Ralph 单线程任务循环
powershell -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -ApiKey "sk-xxx"
```

---

## 任务状态管理

```powershell
# 重置所有 blocked/in_progress 任务为 pending（重新派发）
python - << 'EOF'
import json, datetime
path = r'd:\code\webnovel-writer\running\feature_list.json'
with open(path, encoding='utf-8') as f:
    data = json.load(f)
now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
count = 0
for t in data['features']:
    if t.get('passes') is True:
        continue
    if t.get('status') in ('blocked', 'in_progress', 'claimed'):
        t['status'] = 'pending'
        t['claimed_by'] = ''
        t['claimed_at'] = ''
        t['started_at'] = ''
        t['blocked_reason'] = ''
        t['human_help_requested'] = False
        t['handoff_requested_at'] = ''
        t['defer_to_tail'] = False
        t['notes'] = (t.get('notes','') + '\n' if t.get('notes') else '') + f'[RESET {now}]'
        count += 1
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
print(f'Reset {count} tasks.')
EOF
```

> Windows 下用脚本文件方式：
> ```powershell
> python C:\Users\wxy\AppData\Local\Temp\reset_tasks.py
> ```

---

## 初始化 / 辅助

```powershell
# 初始化 worktree 等环境
powershell -ExecutionPolicy Bypass -File running/init.ps1

# Codex gateway 代理桥接（如需要）
python running/codex-gateway-bridge.py
```

---

## 环境信息

| 项目 | 值 |
|------|----|
| Codex 可执行 | `D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe` |
| Codex 版本 | 1.3.0 |
| API Base URL | `https://api.asxs.top/v1` |
| Python | `C:\Python314\python.exe` |
| Windows Terminal | `wt.exe` |
| 任务文件 | `running/feature_list.json` |
| 会话目录 | `running/sessions/` |
| Worktree 根目录 | `.worktrees/sisyphus/` |
| Dispatcher 日志 | `running/log/dispatcher-out.txt` |

---

## 快速参考

```powershell
# 最常用：一键启动全套
powershell -ExecutionPolicy Bypass -File running/open-dashboard.ps1 -ApiKey "sk-db4420e5de254a1467cc5cfb1a845e13"
```
