"""watch-logs.py — 类 Codex CLI 实时多 Agent 对话面板

像看真正的 codex cli 一样，实时流式渲染每个子 agent 的输出：
  - 区分 thinking / tool-call / assistant-message / error 等块
  - 每个 agent 独立面板，颜色区分
  - 右侧永远显示任务状态摘要
  - 实时 tail，无闪烁

用法:
    python watch-logs.py [interval_seconds]

依赖:
    pip install rich
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("缺少 rich。运行: pip install rich")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.dirname(BASE_DIR)
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
WORKTREES    = os.path.join(REPO_ROOT, ".worktrees", "sisyphus")
DISP_OUT     = os.path.join(BASE_DIR, "log", "dispatcher-out.txt")
DISP_ERR     = os.path.join(BASE_DIR, "log", "dispatcher-err.txt")
FEATURE_LIST = os.path.join(BASE_DIR, "feature_list.json")

MAX_AGENT_PANELS = 3   # 最多同时显示几个 agent
PANEL_LINES      = 32  # 每个面板显示行数

# ---------------------------------------------------------------------------
# 颜色主题（仿 codex-cli 配色）
# ---------------------------------------------------------------------------
AGENT_COLORS = ["#00d7ff", "#00ff87", "#ffaf00", "#ff5f87", "#af87ff"]
STATUS_COLOR = {
    "pending":     "grey50",
    "in_progress": "cyan",
    "done":        "green",
    "blocked":     "red",
    "claimed":     "yellow",
}

# ---------------------------------------------------------------------------
# ANSI 清除
# ---------------------------------------------------------------------------
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

def strip_ansi(s: str) -> str:
    return _ANSI.sub("", s)

# ---------------------------------------------------------------------------
# Codex 输出行解析
# 支持识别的格式：
#   - [thinking] ...
#   - [tool: name] args
#   - Running tool_name / Calling tool_name
#   - [tool_result] ...
#   - Assistant: ...
#   - Error: ...
#   - PASS / FAIL
#   - JSON 行（codex structured output）
# ---------------------------------------------------------------------------
RE_THINKING  = re.compile(r"^\[thinking\]\s*", re.I)
RE_TOOL_CALL = re.compile(r"^\[tool:\s*([\w_]+)\]\s*(.*)", re.I)
RE_TOOL_RUN  = re.compile(r"^(?:Running|Executing|Calling|Using)\s+(?:tool\s+)?[`]?([\w_]+)[`]?\b", re.I)
RE_TOOL_RES  = re.compile(r"^\[tool_result\]\s*", re.I)
RE_ASSISTANT = re.compile(r"^(?:Assistant|Response):\s*", re.I)
RE_ERROR     = re.compile(r"^(?:Error|ERROR|error):\s*", re.I)
RE_PASS      = re.compile(r"\bPASS\b")
RE_FAIL      = re.compile(r"\bFAIL\b")
RE_JSON_LINE = re.compile(r'^\s*[\[{]')


def classify_line(raw: str) -> Tuple[str, str]:
    """返回 (kind, display_text)。kind in: thinking/tool/tool_result/assistant/error/pass/fail/json/plain"""
    line = strip_ansi(raw).rstrip()
    if not line:
        return "blank", ""
    if RE_THINKING.match(line):
        return "thinking", line
    m = RE_TOOL_CALL.match(line)
    if m:
        return "tool", line
    if RE_TOOL_RUN.match(line):
        return "tool", line
    if RE_TOOL_RES.match(line):
        return "tool_result", line
    if RE_ASSISTANT.match(line):
        return "assistant", line
    if RE_ERROR.match(line):
        return "error", line
    if RE_PASS.search(line) and len(line) < 30:
        return "pass", line
    if RE_FAIL.search(line) and len(line) < 30:
        return "fail", line
    if RE_JSON_LINE.match(line):
        return "json", line
    return "plain", line


KIND_STYLE: Dict[str, str] = {
    "thinking":    "italic #888888",
    "tool":        "bold #ffaf00",
    "tool_result": "#5fd7ff",
    "assistant":   "bold white",
    "error":       "bold red",
    "pass":        "bold green",
    "fail":        "bold red",
    "json":        "#afd7af",
    "plain":       "white",
    "blank":       "",
}

KIND_PREFIX: Dict[str, str] = {
    "thinking":    "  ◦ ",
    "tool":        "  ⚙  ",
    "tool_result": "  ← ",
    "assistant":   "  ▶ ",
    "error":       "  ✗ ",
    "pass":        "  ✓ ",
    "fail":        "  ✗ ",
    "json":        "  {} ",
    "plain":       "     ",
    "blank":       "",
}

# ---------------------------------------------------------------------------
# 文件读取（带 mtime 缓存，tail N 行）
# ---------------------------------------------------------------------------
_file_cache: Dict[str, Tuple[float, List[str]]] = {}


def tail_lines(path: str, n: int = 200) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        mtime = os.path.getmtime(path)
        cm, cc = _file_cache.get(path, (0.0, []))
        if mtime == cm:
            return cc[-n:]
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        result = [l.rstrip("\n") for l in lines]
        _file_cache[path] = (mtime, result)
        return result[-n:]
    except Exception:
        return []


def tail_text(path: str, n: int = 40) -> str:
    lines = tail_lines(path, n)
    return "\n".join(lines) if lines else "(empty)"


# ---------------------------------------------------------------------------
# 把日志行列表渲染成 rich Text（带语法高亮）
# ---------------------------------------------------------------------------
def render_log_lines(lines: List[str], max_lines: int = PANEL_LINES) -> Text:
    text = Text()
    visible = lines[-max_lines:] if len(lines) > max_lines else lines
    for raw in visible:
        kind, content = classify_line(raw)
        if kind == "blank":
            text.append("\n")
            continue
        prefix = KIND_PREFIX.get(kind, "     ")
        style  = KIND_STYLE.get(kind, "white")
        # 长行截断
        display = content[:160] + ("…" if len(content) > 160 else "")
        text.append(prefix + display + "\n", style=style)
    return text


# ---------------------------------------------------------------------------
# 发现活跃的 agent 会话
# ---------------------------------------------------------------------------
def get_active_sessions() -> List[Dict]:
    """返回最近活跃的 session 信息列表，按修改时间倒序。"""
    if not os.path.isdir(SESSIONS_DIR):
        return []
    entries = []
    for name in os.listdir(SESSIONS_DIR):
        sp = os.path.join(SESSIONS_DIR, name)
        if not os.path.isdir(sp):
            continue
        # 找最新日志文件
        best_log: Optional[str] = None
        best_mtime = 0.0
        for fn in ("coding-output.log", "evaluator-output.log", "codex-output.log"):
            fp = os.path.join(sp, fn)
            if os.path.exists(fp):
                try:
                    mt = os.path.getmtime(fp)
                    if mt > best_mtime:
                        best_mtime = mt
                        best_log = fp
                except OSError:
                    pass
        if best_log is None:
            continue
        stage = "eval" if "evaluator" in (best_log or "") else "code"
        # 从名字里提取 task id（格式如 20260328-052204-02-T015）
        parts = name.split("-")
        task_id = parts[-1] if parts else name
        entries.append({
            "name":    name,
            "task_id": task_id,
            "stage":   stage,
            "log":     best_log,
            "mtime":   best_mtime,
        })
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries[:MAX_AGENT_PANELS]


# ---------------------------------------------------------------------------
# 任务状态摘要（右侧小表格）
# ---------------------------------------------------------------------------
def build_status_panel() -> Panel:
    features: List[Dict] = []
    try:
        with open(FEATURE_LIST, encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
    except Exception:
        pass

    total   = len(features)
    done    = sum(1 for t in features if t.get("passes") is True)
    running = sum(1 for t in features if t.get("status") == "in_progress")
    blocked = sum(1 for t in features if t.get("status") == "blocked")
    pending = sum(1 for t in features if t.get("status") == "pending")

    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("ID",     style="bold",  width=6)
    table.add_column("Status", width=11)
    table.add_column("Title",  no_wrap=True)

    # 只显示活跃 / 最近关注的任务（in_progress 优先，然后 pending，最多 12 条）
    ordered = sorted(
        features,
        key=lambda t: (
            0 if t.get("status") == "in_progress" else
            1 if t.get("status") == "claimed" else
            2 if t.get("status") == "pending" else
            3 if t.get("status") == "blocked" else 4,
            t.get("priority", 99)
        )
    )[:14]

    for t in ordered:
        status = t.get("status", "pending")
        color  = STATUS_COLOR.get(status, "white")
        tick   = "[green]✓[/]" if t.get("passes") else " "
        title  = (t.get("title") or "")[:35]
        table.add_row(
            t.get("id", ""),
            Text(status, style=color),
            title,
        )

    now = time.strftime("%H:%M:%S")
    summary = Text()
    summary.append(f"{now}  ", style="dim")
    summary.append(f"{done}/{total} done ", style="bold green")
    summary.append(f"| {running} running ", style="cyan")
    summary.append(f"| {blocked} blocked ", style="red")
    summary.append(f"| {pending} pending", style="grey50")

    return Panel(
        Group(summary, Text(""), table),
        title="[bold]Task Queue[/]",
        border_style="#444444",
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Dispatcher 面板
# ---------------------------------------------------------------------------
def build_dispatcher_panel(lines: int = 25) -> Panel:
    disp_lines = tail_lines(DISP_OUT, lines)
    err_lines  = tail_lines(DISP_ERR, 8)

    combined = list(disp_lines)
    if err_lines:
        combined.append("--- STDERR ---")
        combined.extend(err_lines)

    content = render_log_lines(combined, lines)
    return Panel(
        content,
        title="[bold white]Sisyphus Dispatcher[/]",
        border_style="white",
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Agent 面板
# ---------------------------------------------------------------------------
def build_agent_panel(session: Dict, color: str, idx: int) -> Panel:
    lines = tail_lines(session["log"], 200)
    content = render_log_lines(lines, PANEL_LINES)

    stage_icon = "⚙" if session["stage"] == "code" else "✔"
    label = f"{stage_icon} {session['task_id']}  [dim]{session['name'][-16:]}[/]"

    return Panel(
        content,
        title=f"[bold]{label}[/]",
        border_style=color,
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# 「等待 agent」占位面板
# ---------------------------------------------------------------------------
def waiting_panel() -> Panel:
    msg = Text()
    msg.append("\n  等待 Agent 启动...\n", style="dim yellow")
    msg.append("\n  sessions/ 目录为空\n", style="dim")
    msg.append("\n  启动命令:\n", style="dim")
    msg.append("  powershell -File running/start-harness.ps1\n", style="bold white")
    return Panel(msg, title="Agent Output", border_style="#333333", padding=(0, 1))


# ---------------------------------------------------------------------------
# 主布局构建
# ---------------------------------------------------------------------------
def build_layout() -> Layout:
    sessions = get_active_sessions()

    layout = Layout()

    # 顶层：左(agent区) + 右(状态区)
    layout.split_row(
        Layout(name="main",   ratio=5),
        Layout(name="status", ratio=2),
    )

    # 右侧：状态面板
    layout["status"].update(build_status_panel())

    # 左侧：上方 dispatcher + 下方 agent 网格
    layout["main"].split_column(
        Layout(name="dispatcher", ratio=2),
        Layout(name="agents",     ratio=3),
    )
    layout["main"]["dispatcher"].update(build_dispatcher_panel(22))

    if not sessions:
        layout["main"]["agents"].update(waiting_panel())
        return layout

    n = len(sessions)
    agents_layout = layout["main"]["agents"]

    if n == 1:
        agents_layout.update(
            build_agent_panel(sessions[0], AGENT_COLORS[0], 0)
        )
    elif n == 2:
        agents_layout.split_row(
            Layout(build_agent_panel(sessions[0], AGENT_COLORS[0], 0), name="a0"),
            Layout(build_agent_panel(sessions[1], AGENT_COLORS[1], 1), name="a1"),
        )
    else:
        agents_layout.split_row(
            Layout(build_agent_panel(sessions[0], AGENT_COLORS[0], 0), name="a0"),
            Layout(build_agent_panel(sessions[1], AGENT_COLORS[1], 1), name="a1"),
            Layout(build_agent_panel(sessions[2], AGENT_COLORS[2], 2), name="a2"),
        )

    return layout


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
def main() -> None:
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
    console = Console()

    console.print(
        "[bold #00d7ff]Codex Multi-Agent Monitor[/]  "
        "[dim]Ctrl+C 退出 | 实时流式渲染[/]"
    )
    time.sleep(0.3)

    try:
        with Live(
            build_layout(),
            console=console,
            refresh_per_second=int(1 / interval) + 1,
            screen=True,
        ) as live:
            while True:
                time.sleep(interval)
                live.update(build_layout())
    except KeyboardInterrupt:
        console.print("\n[dim]已退出。[/]")


if __name__ == "__main__":
    main()
