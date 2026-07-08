# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Project Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.

"""Standalone MCP-compatible HTTP server for Project Librarian state."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.config import load_config
from app.indexer.index_manager import IndexManager
from app.search.search_engine import search_snapshot

AUTH_HEADER_NAME = "X-Project-Librarian-Token"


def _build_probe_payload(host: str, port: int, token_required: bool) -> dict[str, object]:
    base = f"http://{host}:{port}"
    return {
        "status": "ok",
        "server": "Project Librarian",
        "auth_required": token_required,
        "transport_configured": "streamable-http",
        "endpoints": {
            "probe": f"{base}/api/mcp-probe",
            "probe_jsonrpc": f"{base}/api/mcp-probe/jsonrpc",
            "status": f"{base}/api/status",
            "search": f"{base}/api/search",
            "refresh": f"{base}/api/server/refresh",
            "shutdown": f"{base}/api/server/shutdown",
        },
        "auth": {"accepted": ["Authorization: Bearer <token>", f"{AUTH_HEADER_NAME}: <token>", "?token=<token>"]},
    }


def run_mcp_server(repo_root: str, output_dir: str, host: str, port: int, auth_token: str = "") -> None:
    """Run blocking HTTP server exposing MCP-compatible probe/status/search endpoints."""
    config = load_config()
    config.project_root = repo_root
    config.output_dir = output_dir
    manager = IndexManager(config=config)
    manager.refresh()
    manager.start_refresh_worker(run_immediately=False)

    token = auth_token.strip()

    class _Handler(BaseHTTPRequestHandler):
        server_version = "ProjectLibrarianMCP/1.0"

        def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _request_token(self, query: dict[str, list[str]]) -> str:
            auth_header = self.headers.get("Authorization", "").strip()
            if auth_header.lower().startswith("bearer "):
                return auth_header[7:].strip()
            custom_header = self.headers.get(AUTH_HEADER_NAME, "").strip()
            if custom_header:
                return custom_header
            return (query.get("token", [""])[0] or "").strip()

        def _check_auth(self, query: dict[str, list[str]]) -> bool:
            if not token:
                return True
            return self._request_token(query) == token

        def _parse_request(self) -> tuple[str, dict[str, list[str]]]:
            parsed = urlparse(self.path)
            return parsed.path, parse_qs(parsed.query)

        def _read_json_body(self) -> dict[str, Any] | None:
            length_raw = self.headers.get("Content-Length", "0").strip()
            length = int(length_raw) if length_raw.isdigit() else 0
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                parsed = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None

        def do_GET(self) -> None:  # noqa: N802 - HTTP method override
            path, query = self._parse_request()
            if not self._check_auth(query):
                self._write_json({"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return

            if path == "/api/mcp-probe":
                self._write_json(_build_probe_payload(host=host, port=port, token_required=bool(token)))
                return

            if path == "/api/status":
                status_payload = manager.refresh_status()
                status_payload["repo_root"] = str(Path(manager.config.project_root).resolve())
                status_payload["output_dir"] = str(Path(manager.config.output_dir))
                self._write_json(status_payload)
                return

            if path == "/api/search":
                query_text = (query.get("q", [""])[0] or "").strip()
                scope = (query.get("scope", ["all"])[0] or "all").strip()
                limit_raw = (query.get("limit", ["20"])[0] or "20").strip()
                limit = int(limit_raw) if limit_raw.isdigit() else 20
                results = search_snapshot(
                    file_corpus=manager.state.file_corpus,
                    symbols=manager.state.symbols,
                    excel_rows=manager.state.excel_rows,
                    query=query_text,
                    scope=scope,
                    limit=max(1, min(limit, 200)),
                )
                self._write_json({"count": len(results), "results": results})
                return

            self._write_json({"error": f"Unknown route: {path}"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - HTTP method override
            path, query = self._parse_request()
            if not self._check_auth(query):
                self._write_json({"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return

            if path == "/api/mcp-probe/jsonrpc":
                payload = self._read_json_body()
                if payload is None:
                    self._write_json(
                        {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON payload"}},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                request_id = payload.get("id")
                method = str(payload.get("method") or "").strip()
                if method in {"mcp.ping", "ping", "rpc.ping"}:
                    self._write_json({"jsonrpc": "2.0", "id": request_id, "result": {"ok": True}})
                    return
                if method in {"mcp.probe", "probe", "rpc.discover"}:
                    self._write_json(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": _build_probe_payload(host=host, port=port, token_required=bool(token)),
                        }
                    )
                    return
                self._write_json(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Unsupported probe method: {method}"},
                    },
                    status=HTTPStatus.NOT_FOUND,
                )
                return

            if path == "/api/server/refresh":
                started = manager.request_refresh_async()
                self._write_json({"ok": True, "started": started})
                return

            if path == "/api/server/shutdown":
                self._write_json({"ok": True, "message": "Shutting down"})
                self.server.shutdown()
                return

            self._write_json({"error": f"Unknown route: {path}"}, status=HTTPStatus.NOT_FOUND)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    httpd = ThreadingHTTPServer((host, port), _Handler)
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        manager.stop_refresh_worker()
        httpd.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Project Librarian MCP-compatible server")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", default="build")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_mcp_server(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        host=args.host,
        port=int(args.port),
        auth_token=args.token,
    )


if __name__ == "__main__":
    main()
