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
            "definition": f"{base}/api/definition",
            "diagnostics": f"{base}/api/diagnostics",
            "refresh": f"{base}/api/server/refresh",
            "shutdown": f"{base}/api/server/shutdown",
        },
        "auth": {"accepted": ["Authorization: Bearer <token>", f"{AUTH_HEADER_NAME}: <token>", "?token=<token>"]},
    }


def run_mcp_server(repo_root: str, output_dir: str, host: str, port: int, auth_token: str = "") -> None:
    """Run blocking HTTP server exposing MCP-compatible probe/status/search endpoints."""
    import threading

    config = load_config()
    config.project_root = repo_root
    config.output_dir = output_dir
    manager = IndexManager(config=config)
    threading.Thread(target=manager.refresh, name="mcp-initial-refresh", daemon=True).start()
    manager.start_refresh_worker(run_immediately=False)

    token = auth_token.strip()

    class _Handler(BaseHTTPRequestHandler):
        server_version = "ProjectLibrarianMCP/1.0"

        def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", f"Content-Type, Authorization, {AUTH_HEADER_NAME}")
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:  # noqa: N802 - HTTP method override
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", f"Content-Type, Authorization, {AUTH_HEADER_NAME}")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _write_dashboard_html(self) -> None:
            raw = DASHBOARD_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
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
            if path in {"/", "/index.html"}:
                self._write_dashboard_html()
                return

            if path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT.value)
                self.end_headers()
                return

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
                status_payload["file_count"] = len(manager.state.file_corpus)
                status_payload["symbol_count"] = len(manager.state.symbols)
                status_payload["excel_row_count"] = len(manager.state.excel_rows)
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

            if path == "/api/definition":
                query_text = (query.get("q", [""])[0] or "").strip()
                results = []
                if query_text:
                    for sym in manager.state.symbols:
                        sym_name = str(sym.get("name", ""))
                        sym_qn = str(sym.get("qualified_name", ""))
                        if sym_name.lower() == query_text.lower() or sym_qn.lower() == query_text.lower():
                            results.append({
                                "name": sym_name,
                                "qualified_name": sym_qn,
                                "kind": sym.get("kind"),
                                "path": sym.get("path"),
                                "line": sym.get("line"),
                                "signature": sym.get("signature"),
                                "doc_summary": sym.get("doc_summary")
                            })
                self._write_json({"count": len(results), "results": results})
                return

            if path == "/api/diagnostics":
                filter_text = (query.get("filter", [""])[0] or "").strip().lower()
                from app.models.anti_pattern_model import load_anti_pattern_config
                output_candidate = Path(manager.config.output_dir)
                repo_root = Path(manager.config.project_root or Path.cwd()).resolve()
                output_dir = output_candidate if output_candidate.is_absolute() else repo_root / output_candidate
                
                config_data = load_anti_pattern_config(output_dir)
                presets = config_data.get("presets", [])
                
                import re
                compiled = []
                for preset in presets:
                    regex_text = str(preset.get("regex", ""))
                    if not regex_text or not preset.get("enabled", True):
                        continue
                    try:
                        compiled.append((preset, re.compile(regex_text)))
                    except re.error:
                        continue
                        
                results = []
                for rel_path, file_text in manager.state.file_corpus.items():
                    if filter_text and filter_text not in rel_path.lower():
                        continue
                    for line_idx, line in enumerate(file_text.splitlines(), start=1):
                        for preset, pattern in compiled:
                            if pattern.search(line):
                                results.append({
                                    "file": rel_path,
                                    "line": line_idx,
                                    "content": line.strip(),
                                    "rule_name": preset.get("name"),
                                    "severity": preset.get("severity"),
                                    "description": preset.get("description"),
                                })
                self._write_json({"count": len(results), "results": results})
                return

            self._write_json({"error": f"Unknown route: {path}"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - HTTP method override
            path, query = self._parse_request()
            if not self._check_auth(query):
                self._write_json({"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return

            if path == "/api/search":
                body = self._read_json_body() or {}
                query_text = str(body.get("q", query.get("q", [""])[0] if "q" in query else "")).strip()
                scope = str(body.get("scope", query.get("scope", ["all"])[0] if "scope" in query else "all")).strip()
                limit_val = body.get("limit")
                if limit_val is not None:
                    try:
                        limit = int(limit_val)
                    except (ValueError, TypeError):
                        limit = 20
                else:
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

            if path == "/api/definition":
                body = self._read_json_body() or {}
                query_text = str(body.get("q", query.get("q", [""])[0] if "q" in query else "")).strip()
                results = []
                if query_text:
                    for sym in manager.state.symbols:
                        sym_name = str(sym.get("name", ""))
                        sym_qn = str(sym.get("qualified_name", ""))
                        if sym_name.lower() == query_text.lower() or sym_qn.lower() == query_text.lower():
                            results.append({
                                "name": sym_name,
                                "qualified_name": sym_qn,
                                "kind": sym.get("kind"),
                                "path": sym.get("path"),
                                "line": sym.get("line"),
                                "signature": sym.get("signature"),
                                "doc_summary": sym.get("doc_summary")
                            })
                self._write_json({"count": len(results), "results": results})
                return

            if path == "/api/diagnostics":
                body = self._read_json_body() or {}
                filter_text = str(body.get("filter", query.get("filter", [""])[0] if "filter" in query else "")).strip().lower()
                from app.models.anti_pattern_model import load_anti_pattern_config
                output_candidate = Path(manager.config.output_dir)
                repo_root = Path(manager.config.project_root or Path.cwd()).resolve()
                output_dir = output_candidate if output_candidate.is_absolute() else repo_root / output_candidate
                
                config_data = load_anti_pattern_config(output_dir)
                presets = config_data.get("presets", [])
                
                import re
                compiled = []
                for preset in presets:
                    regex_text = str(preset.get("regex", ""))
                    if not regex_text or not preset.get("enabled", True):
                        continue
                    try:
                        compiled.append((preset, re.compile(regex_text)))
                    except re.error:
                        continue
                        
                results = []
                for rel_path, file_text in manager.state.file_corpus.items():
                    if filter_text and filter_text not in rel_path.lower():
                        continue
                    for line_idx, line in enumerate(file_text.splitlines(), start=1):
                        for preset, pattern in compiled:
                            if pattern.search(line):
                                results.append({
                                    "file": rel_path,
                                    "line": line_idx,
                                    "content": line.strip(),
                                    "rule_name": preset.get("name"),
                                    "severity": preset.get("severity"),
                                    "description": preset.get("description"),
                                })
                self._write_json({"count": len(results), "results": results})
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


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Librarian MCP Dashboard</title>
    <style>
        :root {
            --bg-color: #0f1115;
            --card-bg: #161a22;
            --text-color: #e6edf3;
            --text-muted: #8d96a0;
            --primary: #2f81f7;
            --primary-hover: #4c94f8;
            --success: #3fb950;
            --error: #f85149;
            --border-color: #30363d;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            line-height: 1.5;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }
        h1 {
            margin: 0;
            font-size: 1.8rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .status-indicator {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
            color: var(--text-muted);
            background: #1c2128;
            padding: 0.3rem 0.8rem;
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }
        .dot {
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--success);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(63, 185, 80, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(63, 185, 80, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(63, 185, 80, 0); }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 1.2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin: 0 0 0.5rem 0;
        }
        .card-value {
            font-size: 1.8rem;
            font-weight: bold;
            margin: 0;
        }
        .sections {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
        }
        @media (max-width: 768px) {
            .sections { grid-template-columns: 1fr; }
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-top: 0;
            margin-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.4rem;
        }
        .playground-form {
            display: flex;
            flex-wrap: wrap;
            gap: 0.8rem;
            margin-bottom: 1.5rem;
        }
        input, select, button {
            background: #1c2128;
            color: var(--text-color);
            border: 1px solid var(--border-color);
            padding: 0.5rem 0.8rem;
            border-radius: 6px;
            font-size: 0.95rem;
            outline: none;
        }
        input:focus, select:focus {
            border-color: var(--primary);
        }
        input[type="text"] {
            flex: 1;
            min-width: 200px;
        }
        button {
            cursor: pointer;
            background-color: var(--primary);
            color: #ffffff;
            border: none;
            font-weight: 500;
            transition: background 0.2s;
        }
        button:hover {
            background-color: var(--primary-hover);
        }
        button.secondary {
            background-color: #21262d;
            border: 1px solid var(--border-color);
            color: var(--text-color);
        }
        button.secondary:hover {
            background-color: #30363d;
        }
        .results-box {
            background-color: #0d1117;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 1rem;
            min-height: 200px;
            max-height: 500px;
            overflow-y: auto;
            font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
        }
        .result-item {
            padding: 0.8rem;
            border-bottom: 1px solid var(--border-color);
        }
        .result-item:last-child {
            border-bottom: none;
        }
        .result-path {
            color: var(--primary);
            font-weight: bold;
            text-decoration: none;
        }
        .result-meta {
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-top: 0.2rem;
        }
        .result-snippet {
            margin-top: 0.5rem;
            background: #161b22;
            padding: 0.5rem;
            border-radius: 4px;
            border-left: 3px solid var(--primary);
        }
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }
        .meta-list {
            list-style: none;
            padding: 0;
            margin: 0;
            font-size: 0.9rem;
        }
        .meta-list li {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border-color);
        }
        .meta-list li:last-child {
            border-bottom: none;
        }
        .meta-label {
            color: var(--text-muted);
        }
        .meta-value {
            font-weight: 500;
            text-align: right;
            word-break: break-all;
        }
        .endpoint-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        .endpoint-table th, .endpoint-table td {
            text-align: left;
            padding: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }
        .endpoint-table th {
            color: var(--text-muted);
        }
        .method {
            display: inline-block;
            padding: 0.1rem 0.4rem;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        .method.get { background-color: rgba(63,185,80,0.15); color: #58a6ff; }
        .method.post { background-color: rgba(248,81,73,0.15); color: #ff7b72; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <svg height="32" viewBox="0 0 16 16" width="32" fill="currentColor"><path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM4.5 11h8a.75.75 0 010 1.5h-8a1 1 0 000 2h8a.75.75 0 010 1.5h-8A2.5 2.5 0 012 13.5v-1A2.5 2.5 0 014.5 11z"></path></svg>
                Project Librarian MCP
            </h1>
            <div class="status-indicator">
                <span class="dot"></span>
                <span>Server Online</span>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <p class="card-title">Files Indexed</p>
                <p class="card-value" id="stat-files">0</p>
            </div>
            <div class="card">
                <p class="card-title">Symbols Indexed</p>
                <p class="card-value" id="stat-symbols">0</p>
            </div>
            <div class="card">
                <p class="card-title">Excel Keyword Rows</p>
                <p class="card-value" id="stat-excel">0</p>
            </div>
            <div class="card">
                <p class="card-title">Skipped Files</p>
                <p class="card-value" id="stat-skipped" style="color: var(--error);">0</p>
            </div>
        </div>

        <div class="sections">
            <div>
                <div class="card" style="margin-bottom: 1.5rem;">
                    <h2 class="section-title">Search Playground</h2>
                    <div class="playground-form">
                        <input type="text" id="search-query" placeholder="Enter search term (e.g. main, def, class)..." />
                        <select id="search-scope">
                            <option value="all">All Scopes</option>
                            <option value="files">Files Only</option>
                            <option value="symbols">Symbols Only</option>
                            <option value="excel">Excel Only</option>
                        </select>
                        <input type="number" id="search-limit" value="10" min="1" max="100" style="width: 60px;" />
                        <button id="btn-search">Search</button>
                    </div>
                    <div class="results-box" id="search-results">Results will appear here...</div>
                </div>

                <div class="card">
                    <h2 class="section-title">Endpoints Reference</h2>
                    <table class="endpoint-table">
                        <thead>
                            <tr>
                                <th>Method</th>
                                <th>Endpoint</th>
                                <th>Description</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><span class="method get">GET</span></td>
                                <td><code>/api/mcp-probe</code></td>
                                <td>Check server status and capability listing</td>
                            </tr>
                            <tr>
                                <td><span class="method get">GET</span></td>
                                <td><code>/api/status</code></td>
                                <td>Retrieve indexing and environment metadata</td>
                            </tr>
                            <tr>
                                <td><span class="method get">GET</span></td>
                                <td><code>/api/search?q=&lt;query&gt;&amp;scope=&lt;scope&gt;</code></td>
                                <td>Search the library index (supports CORS)</td>
                            </tr>
                            <tr>
                                <td><span class="method post">POST</span></td>
                                <td><code>/api/search</code></td>
                                <td>Search index using JSON body payload</td>
                            </tr>
                            <tr>
                                <td><span class="method post">POST</span></td>
                                <td><code>/api/server/refresh</code></td>
                                <td>Trigger asynchronous background re-index</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="sidebar">
                <div class="card">
                    <h2 class="section-title">Authentication Settings</h2>
                    <div style="margin-bottom: 1rem;">
                        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 0.3rem;">Access Token:</label>
                        <input type="password" id="auth-token" placeholder="Optional Auth Token..." style="width: calc(100% - 1.6rem);" />
                    </div>
                    <button id="btn-save-token" class="secondary" style="width: 100%;">Save Token Locally</button>
                </div>

                <div class="card">
                    <h2 class="section-title">Server Info</h2>
                    <ul class="meta-list">
                        <li>
                            <span class="meta-label">Project Root</span>
                            <span class="meta-value" id="meta-root">-</span>
                        </li>
                        <li>
                            <span class="meta-label">Output Directory</span>
                            <span class="meta-value" id="meta-output">-</span>
                        </li>
                        <li>
                            <span class="meta-label">Last Refresh</span>
                            <span class="meta-value" id="meta-last-refresh">-</span>
                        </li>
                        <li>
                            <span class="meta-label">Refresh Worker</span>
                            <span class="meta-value" id="meta-worker">-</span>
                        </li>
                    </ul>
                    <button id="btn-refresh" class="secondary" style="width: 100%; margin-top: 1rem; border-color: var(--primary); color: #58a6ff;">Trigger Re-index</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const elFiles = document.getElementById('stat-files');
        const elSymbols = document.getElementById('stat-symbols');
        const elExcel = document.getElementById('stat-excel');
        const elSkipped = document.getElementById('stat-skipped');
        const elRoot = document.getElementById('meta-root');
        const elOutput = document.getElementById('meta-output');
        const elLastRefresh = document.getElementById('meta-last-refresh');
        const elWorker = document.getElementById('meta-worker');
        const elTokenInput = document.getElementById('auth-token');
        const elBtnSaveToken = document.getElementById('btn-save-token');
        const elBtnSearch = document.getElementById('btn-search');
        const elBtnRefresh = document.getElementById('btn-refresh');
        const elQueryInput = document.getElementById('search-query');
        const elScopeSelect = document.getElementById('search-scope');
        const elLimitInput = document.getElementById('search-limit');
        const elResults = document.getElementById('search-results');

        // Load saved token from localStorage
        const storedToken = localStorage.getItem('mcp_auth_token') || '';
        elTokenInput.value = storedToken;

        elBtnSaveToken.addEventListener('click', () => {
            localStorage.setItem('mcp_auth_token', elTokenInput.value.trim());
            alert('Auth token saved locally for browser playground requests.');
            loadStatus();
        });

        function getHeaders() {
            const headers = { 'Accept': 'application/json' };
            const token = elTokenInput.value.trim();
            if (token) {
                headers['Authorization'] = 'Bearer ' + token;
            }
            return headers;
        }

        async function loadStatus() {
            try {
                const res = await fetch('/api/status', { headers: getHeaders() });
                if (res.status === 401) {
                    elResults.innerHTML = '<span style="color: var(--error)">Unauthorized. Please enter the Access Token in the settings sidebar to load details.</span>';
                    return;
                }
                const data = await res.json();
                elFiles.textContent = data.file_count || 0;
                elSymbols.textContent = data.symbol_count || 0;
                elExcel.textContent = data.excel_row_count || 0;
                elSkipped.textContent = data.skipped_count || 0;
                elRoot.textContent = data.repo_root || '-';
                elOutput.textContent = data.output_dir || '-';
                elLastRefresh.textContent = data.last_refresh_at ? new Date(data.last_refresh_at * 1000).toLocaleString() : 'Never';
                elWorker.textContent = data.worker_running ? 'Active (' + data.interval_seconds + 's)' : 'Inactive';
            } catch (err) {
                console.error('Error fetching status:', err);
            }
        }

        async function triggerSearch() {
            const query = elQueryInput.value.trim();
            const scope = elScopeSelect.value;
            const limit = parseInt(elLimitInput.value) || 10;

            elResults.textContent = 'Searching...';

            try {
                // We will use the POST endpoint to demonstrate its capabilities!
                const res = await fetch('/api/search', {
                    method: 'POST',
                    headers: {
                        ...getHeaders(),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ q: query, scope: scope, limit: limit })
                });

                if (res.status === 401) {
                    elResults.innerHTML = '<span style="color: var(--error)">Unauthorized. Verify the Access Token.</span>';
                    return;
                }

                if (!res.ok) {
                    const errorData = await res.json();
                    elResults.innerHTML = '<span style="color: var(--error)">Search failed: ' + (errorData.error || res.statusText) + '</span>';
                    return;
                }

                const data = await res.json();
                if (!data.results || data.results.length === 0) {
                    elResults.textContent = 'No results found.';
                    return;
                }

                elResults.innerHTML = '';
                data.results.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'result-item';
                    
                    const header = document.createElement('div');
                    header.style.display = 'flex';
                    header.style.justifyContent = 'space-between';
                    
                    const pathSpan = document.createElement('span');
                    pathSpan.className = 'result-path';
                    pathSpan.textContent = item.path || 'Unknown';
                    
                    const typeSpan = document.createElement('span');
                    typeSpan.className = 'result-meta';
                    typeSpan.textContent = '[' + (item.type || 'file') + ']';
                    
                    header.appendChild(pathSpan);
                    header.appendChild(typeSpan);
                    div.appendChild(header);

                    if (item.symbol) {
                        const sym = document.createElement('div');
                        sym.className = 'result-meta';
                        sym.innerHTML = 'Symbol: <strong style="color: #ff7b72">' + item.symbol + '</strong> (' + item.kind + ')';
                        div.appendChild(sym);
                    }

                    if (item.matches) {
                        const snip = document.createElement('div');
                        snip.className = 'result-snippet';
                        snip.textContent = item.matches.join('\\n');
                        div.appendChild(snip);
                    }
                    
                    elResults.appendChild(div);
                });
            } catch (err) {
                elResults.innerHTML = '<span style="color: var(--error)">Error during search: ' + err.message + '</span>';
            }
        }

        elBtnSearch.addEventListener('click', triggerSearch);
        elQueryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') triggerSearch();
        });

        elBtnRefresh.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/server/refresh', {
                    method: 'POST',
                    headers: getHeaders()
                });
                if (res.status === 401) {
                    alert('Unauthorized to trigger re-index.');
                    return;
                }
                const data = await res.json();
                if (data.ok) {
                    alert('Re-index triggered successfully.');
                    setTimeout(loadStatus, 1000);
                } else {
                    alert('Failed to trigger re-index.');
                }
            } catch (err) {
                alert('Error: ' + err.message);
            }
        });

        // Initialize status details load
        loadStatus();
    </script>
</body>
</html>"""


if __name__ == "__main__":
    main()

