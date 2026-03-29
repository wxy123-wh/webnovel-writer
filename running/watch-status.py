"""watch-status.py — 实时刷新任务状态面板（基于 rich.Live，无闪烁）

用法:
    python watch-status.py [interval_seconds]
默认轮询间隔 2 秒；仅在 feature_list.json 发生变化时重新渲染。
"""
import json
import os
import sys
import time
from datetime import datetime

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
    from rich.panel import Panel
    from rich.columns import Columns
except ImportError:
    print("提示: 缺少 rich 依赖。请先运行: pip install rich")
    sys.exit(1)

DATA_PATH = os.path.join(os.path.dirname(__file__), "feature_list.json")

STATUS_STYLE = {
    "pending":     "grey50",
    "claimed":     "yellow",
    "in_progress": "cyan",
    "done":        "green",
    "blocked":     "red",
}


def load() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_table(data: dict) -> Panel:
    features = data.get("features", [])
    total   = len(features)
    done    = sum(1 for t in features if t.get("passes") is True)
    inprog  = sum(1 for t in features if t.get("status") == "in_progress")
    pending = sum(1 for t in features if t.get("status") == "pending")
    blocked = sum(1 for t in features if t.get("status") == "blocked")

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("ID",     style="bold",   width=6)
    table.add_column("Status", width=12)
    table.add_column("P",      justify="right", width=3)
    table.add_column("MS",     width=4)
    table.add_column("✓",      justify="center", width=2)
    table.add_column("Title",  no_wrap=True)

    order = {"in_progress": 0, "claimed": 1, "pending": 2, "done": 3, "blocked": 4}
    sorted_features = sorted(
        features,
        key=lambda t: (order.get(t.get("status", "pending"), 9), t.get("priority", 99)),
    )

    for t in sorted_features:
        status = t.get("status", "pending")
        style  = STATUS_STYLE.get(status, "")
        tick   = Text("v", style="green") if t.get("passes") else Text(" ")
        title  = t.get("title", "")[:60]
        table.add_row(
            t["id"],
            Text(status, style=style),
            str(t.get("priority", 0)),
            t.get("milestone", ""),
            tick,
            title,
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        f"{now}  |  [green]{done}/{total} passed[/]  |  "
        f"[cyan]{inprog} running[/]  |  [grey50]{pending} pending[/]  |  "
        f"[red]{blocked} blocked[/]"
    )

    # 最近会话片段
    sessions_dir = os.path.join(os.path.dirname(__file__), "sessions")
    session_lines = []
    if os.path.isdir(sessions_dir):
        sessions = sorted(
            (s for s in os.listdir(sessions_dir)
             if os.path.isdir(os.path.join(sessions_dir, s))),
            reverse=True,
        )[:3]
        for s in sessions:
            log   = os.path.join(sessions_dir, s, "codex-output.log")
            last  = os.path.join(sessions_dir, s, "last-message.txt")
            size  = f" ({os.path.getsize(log)}b)" if os.path.exists(log) else ""
            snippet = ""
            if os.path.exists(last):
                try:
                    snippet = (
                        open(last, encoding="utf-8", errors="replace")
                        .read(120)
                        .replace("\n", " ")
                        .strip()
                    )
                except Exception:
                    pass
            session_lines.append(f"  [bold]{s}[/]{size}")
            if snippet:
                session_lines.append(f"    [dim]{snippet}[/]")

    body_parts = [summary, "", table]
    if session_lines:
        body_parts.append("")
        body_parts.append(Text.from_markup("[bold]Recent sessions:[/]"))
        for line in session_lines:
            body_parts.append(Text.from_markup(line))

    from rich.console import Group
    return Panel(
        Group(*body_parts),
        title="[bold]webnovel-writer Harness Status[/]",
        border_style="blue",
        subtitle="[dim]Ctrl+C to stop[/]",
    )


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    last_mtime = 0.0
    last_data: dict = {"features": []}

    console = Console()

    def get_renderable():
        nonlocal last_mtime, last_data
        try:
            mtime = os.path.getmtime(DATA_PATH)
            if mtime != last_mtime:
                last_data  = load()
                last_mtime = mtime
        except Exception:
            pass
        return build_table(last_data)

    try:
        with Live(
            get_renderable(),
            console=console,
            refresh_per_second=4,
            screen=True,
        ) as live:
            while True:
                time.sleep(interval)
                live.update(get_renderable())
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/]")


if __name__ == "__main__":
    main()
