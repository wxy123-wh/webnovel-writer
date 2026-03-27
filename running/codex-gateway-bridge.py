#!/usr/bin/env python
"""
Minimal HTTP bridge for Codex -> custom gateway compatibility.

Codex sends OpenAI-style requests to a local plain-HTTP endpoint.
This bridge forwards them to the configured upstream HTTPS gateway and
returns bytes either as streaming chunks or as one buffered payload.
"""

from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.parse import urljoin

import requests


LOG = logging.getLogger("codex-gateway-bridge")


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        upstream_base: str,
        connect_timeout: float,
        read_timeout: float,
        response_mode: str,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.upstream_base = upstream_base.rstrip("/") + "/"
        self.timeout_tuple = (connect_timeout, read_timeout)
        self.response_mode = response_mode
        self.session = requests.Session()
        self.session.trust_env = False


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def do_PUT(self) -> None:  # noqa: N802
        self._proxy()

    def do_PATCH(self) -> None:  # noqa: N802
        self._proxy()

    def do_DELETE(self) -> None:  # noqa: N802
        self._proxy()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._proxy()

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("%s - %s", self.client_address[0], fmt % args)

    def _proxy(self) -> None:
        server = self.server
        assert isinstance(server, ProxyServer)

        body = self._read_body()
        target_url = urljoin(server.upstream_base, self.path.lstrip("/"))
        headers = self._filtered_request_headers()

        LOG.debug("Forward %s %s -> %s", self.command, self.path, target_url)
        try:
            upstream = server.session.request(
                method=self.command,
                url=target_url,
                headers=headers,
                data=body,
                stream=(server.response_mode == "stream"),
                timeout=server.timeout_tuple,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            LOG.warning("Upstream request failed: %s %s (%s)", self.command, target_url, exc)
            self._write_json_error(502, "upstream_request_failed", str(exc))
            return

        try:
            self.send_response(upstream.status_code)
            for key, value in upstream.headers.items():
                lk = key.lower()
                if lk in HOP_BY_HOP_HEADERS or lk == "content-length":
                    continue
                self.send_header(key, value)
            payload: bytes | None = None
            if server.response_mode == "buffered":
                payload = upstream.content
                self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()

            if server.response_mode == "stream":
                self._stream_response(upstream.iter_content(chunk_size=8192))
            else:
                self._write_payload(payload)
        finally:
            upstream.close()

    def _read_body(self) -> bytes | None:
        raw_len = self.headers.get("Content-Length")
        if not raw_len:
            return None
        try:
            length = int(raw_len)
        except ValueError:
            return None
        if length <= 0:
            return None
        return self.rfile.read(length)

    def _filtered_request_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            lk = key.lower()
            if lk in HOP_BY_HOP_HEADERS:
                continue
            if lk in {"host", "content-length"}:
                continue
            headers[key] = value
        return headers

    def _stream_response(self, chunks: Iterable[bytes]) -> None:
        try:
            for chunk in chunks:
                if not chunk:
                    continue
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("Client disconnected during response streaming.")

    def _write_payload(self, payload: bytes | None) -> None:
        if not payload:
            return
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("Client disconnected during buffered response write.")

    def _write_json_error(self, status_code: int, code: str, message: str) -> None:
        payload = json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex gateway compatibility bridge")
    parser.add_argument("--listen-host", default="127.0.0.1", help="Listen host (default: 127.0.0.1)")
    parser.add_argument("--listen-port", type=int, default=18888, help="Listen port (default: 18888)")
    parser.add_argument("--upstream-base", required=True, help="Upstream API base URL, e.g. https://api.asxs.top/v1")
    parser.add_argument("--connect-timeout", type=float, default=10.0, help="Upstream connect timeout seconds")
    parser.add_argument("--read-timeout", type=float, default=600.0, help="Upstream read timeout seconds")
    parser.add_argument(
        "--response-mode",
        default="buffered",
        choices=["buffered", "stream"],
        help="Bridge response transfer mode (default: buffered)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    server = ProxyServer(
        server_address=(args.listen_host, args.listen_port),
        request_handler_class=ProxyHandler,
        upstream_base=args.upstream_base,
        connect_timeout=args.connect_timeout,
        read_timeout=args.read_timeout,
        response_mode=args.response_mode,
    )

    LOG.info(
        "Bridge listening on http://%s:%s -> %s (response_mode=%s)",
        args.listen_host,
        args.listen_port,
        args.upstream_base,
        args.response_mode,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        LOG.info("Bridge interrupted; shutting down.")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
