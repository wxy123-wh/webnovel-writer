"""
Dashboard 启动脚本

用法：
    python -m dashboard.server --project-root /path/to/novel-project
    python -m dashboard.server                   # 自动从 .codex 指针读取
"""

import argparse
import importlib
import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def _resolve_project_root(cli_root: str | None) -> Path:
    """复用 scripts/project_locator.py 中的统一解析逻辑。"""
    package_root = Path(__file__).resolve().parents[1]
    scripts_root = package_root / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))

    try:
        project_locator = importlib.import_module("project_locator")
    except Exception as exc:
        print(f"ERROR: 无法导入 project_locator 以解析项目路径: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        resolve_project_root = getattr(project_locator, "resolve_project_root")
        root = resolve_project_root(cli_root, cwd=Path.cwd())
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Hint: run `powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot <PROJECT_ROOT> -StartDashboard` from the repo root.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: 项目路径解析失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    state_path = root / ".webnovel" / "state.json"
    if not state_path.is_file():
        print(f"ERROR: 项目根目录缺少 .webnovel/state.json: {root}", file=sys.stderr)
        sys.exit(1)
    return root


def _bootstrap_index_if_needed(project_root: Path) -> None:
    """缺失 index.db 时，调用统一 CLI 进行一次最小初始化（index stats）。"""
    index_db = project_root / ".webnovel" / "index.db"
    if index_db.is_file():
        return

    scripts_entry = Path(__file__).resolve().parents[1] / "scripts" / "webnovel.py"
    if not scripts_entry.is_file():
        print(
            f"WARNING: 未找到统一 CLI 入口，无法自动初始化 index.db: {scripts_entry}",
            file=sys.stderr,
        )
        return

    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(scripts_entry),
        "--project-root",
        str(project_root),
        "index",
        "stats",
    ]
    # P0-D 修复：添加 timeout=30 防止子进程挂起导致 Dashboard 启动永久阻塞
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("WARNING: 自动初始化 index.db 超时（>30s），已跳过", file=sys.stderr)
        return
    if proc.returncode == 0 and index_db.is_file():
        print("检测到缺失 index.db，已自动初始化。")
        return

    stderr_tail = (proc.stderr or "").strip()
    stdout_tail = (proc.stdout or "").strip()
    detail = stderr_tail or stdout_tail or f"exit_code={proc.returncode}"
    print(f"WARNING: 自动初始化 index.db 失败：{detail}", file=sys.stderr)


def _resolve_basic_auth(raw_value: str | None) -> tuple[str, str] | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    username, sep, password = value.partition(":")
    if not sep or not username or not password:
        print("ERROR: --basic-auth / WEBNOVEL_DASHBOARD_BASIC_AUTH 必须是 user:password 格式", file=sys.stderr)
        sys.exit(2)
    return username, password


def main():
    parser = argparse.ArgumentParser(description="Webnovel Dashboard Server")
    parser.add_argument("--project-root", type=str, default=None, help="小说项目根目录")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument(
        "--no-bootstrap-index",
        action="store_true",
        help="不自动初始化缺失的 .webnovel/index.db",
    )
    # P0-A 修复：允许通过 CLI 指定 CORS 来源，避免全开放安全漏洞
    parser.add_argument(
        "--cors-origin",
        action="append",
        dest="cors_origins",
        metavar="ORIGIN",
        help="允许的 CORS 来源（可多次指定），默认仅 http://localhost:{port} 和 http://127.0.0.1:{port}",
    )
    # P2-C 修复：日志级别和格式参数
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别，默认 INFO",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="输出 JSON 格式日志（生产环境推荐）",
    )
    parser.add_argument(
        "--basic-auth",
        default=None,
        help="可选的 Basic Auth 凭据，格式 user:password；生产环境更推荐用 WEBNOVEL_DASHBOARD_BASIC_AUTH 环境变量",
    )
    args = parser.parse_args()

    # P2-C 修复：尽早初始化结构化日志
    from .logging_config import get_logger, setup_logging
    setup_logging(level=args.log_level, json_output=args.log_json)
    logger = get_logger("dashboard.server")

    project_root = _resolve_project_root(args.project_root)
    logger.info("项目路径已加载", extra={"project_root": str(project_root)})
    if not args.no_bootstrap_index:
        _bootstrap_index_if_needed(project_root)

    # 延迟导入，以便先处理路径
    import uvicorn

    from .app import create_app

    # P0-A 修复：构建最终 CORS 来源列表
    allowed_origins = args.cors_origins or [f"http://localhost:{args.port}", f"http://127.0.0.1:{args.port}"]

    basic_auth = _resolve_basic_auth(args.basic_auth or os.environ.get("WEBNOVEL_DASHBOARD_BASIC_AUTH"))

    app = create_app(project_root, allowed_origins=allowed_origins, basic_auth_credentials=basic_auth)

    url = f"http://{args.host}:{args.port}"
    logger.info("Dashboard 已启动", extra={"url": url, "cors": allowed_origins})
    print(f"Dashboard 启动: {url}")

    if not args.no_browser:
        webbrowser.open(url)

    # P2-C 修复：uvicorn 日志级别与 CLI 参数保持一致
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
