# Copyright (C) 2026 The Librarian contributors
#
# This file is part of The Librarian.
#
# The Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with The Librarian. If not, see <https://www.gnu.org/licenses/>.
"""Smoke tests for the standalone FastAPI/FastMCP-based server runtime."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_probe(port: int, timeout_seconds: float = 8.0) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/mcp-probe", timeout=1.5) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = str(exc)
            time.sleep(0.15)
    raise RuntimeError(f"MCP probe did not become available: {last_error}")


def test_mcp_server_process_serves_probe_and_search(app_config):
    port = _free_port()
    command = [
        sys.executable,
        "-m",
        "app.models.librarian_mcp_server",
        "--repo-root",
        app_config.project_root,
        "--output-dir",
        "build",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(  # noqa: S603 - controlled test command
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        probe = _wait_for_probe(port)
        assert probe["status"] == "ok"
        assert probe["transport_configured"] == "streamable-http"

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/search?q=sample&scope=files&limit=3",
            timeout=2.0,
        ) as response:
            assert response.headers.get("Access-Control-Allow-Origin") == "*"
            payload = json.loads(response.read().decode("utf-8"))
        assert isinstance(payload.get("count"), int)
        assert isinstance(payload.get("results"), list)

        # Check OPTIONS request
        req_options = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/search",
            method="OPTIONS"
        )
        with urllib.request.urlopen(req_options, timeout=2.0) as response:
            assert response.headers.get("Access-Control-Allow-Origin") == "*"
            assert "POST" in response.headers.get("Access-Control-Allow-Methods", "")

        # Check POST search request with JSON body
        req_post = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/search",
            data=json.dumps({"q": "sample", "scope": "files", "limit": 3}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_post, timeout=2.0) as response:
            assert response.headers.get("Access-Control-Allow-Origin") == "*"
            payload = json.loads(response.read().decode("utf-8"))
        assert isinstance(payload.get("count"), int)
        assert isinstance(payload.get("results"), list)

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_mcp_server_requires_token_when_configured(app_config):
    port = _free_port()
    token = "top-secret-token"
    command = [
        sys.executable,
        "-m",
        "app.models.librarian_mcp_server",
        "--repo-root",
        app_config.project_root,
        "--output-dir",
        "build",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--token",
        token,
    ]
    process = subprocess.Popen(  # noqa: S603 - controlled test command
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        endpoint = f"http://127.0.0.1:{port}/api/mcp-probe"

        deadline = time.time() + 8.0
        while time.time() < deadline:
            try:
                request = urllib.request.Request(endpoint, method="GET")
                urllib.request.urlopen(request, timeout=1.5)
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    break
            except urllib.error.URLError:
                pass
            time.sleep(0.15)
        else:
            raise RuntimeError("Expected unauthorized response was not returned.")

        authorized_request = urllib.request.Request(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        with urllib.request.urlopen(authorized_request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "ok"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_mcp_server_ast_and_cst_routes(app_config):
    port = _free_port()
    command = [
        sys.executable,
        "-m",
        "app.models.librarian_mcp_server",
        "--repo-root",
        app_config.project_root,
        "--output-dir",
        "build",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(  # noqa: S603 - controlled test command
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_probe(port)

        p_root = Path(app_config.project_root)
        py_files = list(p_root.rglob("*.py"))
        assert len(py_files) > 0, "No python files found in project root to parse"
        target_rel = py_files[0].relative_to(p_root).as_posix()

        endpoint = f"http://127.0.0.1:{port}/api/ast?path={target_rel}"
        with urllib.request.urlopen(endpoint, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert "path" in payload
        assert "classes" in payload
        assert "functions" in payload

        # Test JSON-RPC search
        rpc_endpoint = f"http://127.0.0.1:{port}/api/mcp-probe/jsonrpc"
        req_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 42,
            "method": "mcp.search",
            "params": {
                "q": "app",
                "scope": "all"
            }
        }).encode("utf-8")
        req = urllib.request.Request(rpc_endpoint, data=req_body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2.0) as response:
            res_payload = json.loads(response.read().decode("utf-8"))
        assert res_payload["id"] == 42
        assert "result" in res_payload
        assert "results" in res_payload["result"]

        # Test JSON-RPC mcp.ast
        ast_req_body = json.dumps({
            "jsonrpc": "2.0",
            "id": 43,
            "method": "mcp.ast",
            "params": {
                "path": target_rel
            }
        }).encode("utf-8")
        ast_req = urllib.request.Request(rpc_endpoint, data=ast_req_body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(ast_req, timeout=2.0) as response:
            ast_res_payload = json.loads(response.read().decode("utf-8"))
        assert ast_res_payload["id"] == 43
        assert "result" in ast_res_payload
        assert ast_res_payload["result"]["path"] == target_rel

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_fastmcp_tools_and_resources_registration(app_config):
    import asyncio
    from app.models.librarian_mcp_server import mcp
    import app.models.librarian_mcp_server as server_mod
    from app.indexer.index_manager import IndexManager
    
    manager = IndexManager(config=app_config)
    manager.refresh()
    server_mod.manager = manager
    
    # Verify tools exist
    tools = asyncio.run(mcp.list_tools())
    tool_names = [t.name for t in tools]
    assert "search_codebase" in tool_names
    assert "audit_triad" in tool_names
    assert "generate_triad_boilerplate" in tool_names

    # Verify resource templates exist
    templates = asyncio.run(mcp.list_resource_templates())
    template_uris = [t.uriTemplate for t in templates]
    assert "file:///{relative_path}" in template_uris


def test_mcp_server_ai_generate_route(app_config, monkeypatch):
    """Test the FastAPI route post_ai_generate with a mocked Ollama HTTP response."""
    import asyncio
    import app.models.librarian_mcp_server as server_mod
    from app.models.librarian_mcp_server import post_ai_generate
    from app.indexer.index_manager import IndexManager

    manager = IndexManager(config=app_config)
    manager.refresh()
    server_mod.manager = manager

    p_root = Path(app_config.project_root)
    m_file = p_root / "book_model.py"
    v_file = p_root / "book_view.py"
    c_file = p_root / "book_controller.py"

    m_file.write_text("class BookModel:\n    pass\n", encoding="utf-8")
    v_file.write_text("class BookView:\n    # AI-request: add reset\n    pass\n", encoding="utf-8")
    c_file.write_text("class BookController:\n    pass\n", encoding="utf-8")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            inner_dict = {
                "model_imports": "",
                "model_additions": "    def reset(self):\n        pass",
                "view_imports": "",
                "view_additions": "",
                "controller_imports": "",
                "controller_additions": "    def handle_reset(self):\n        pass"
            }
            return json.dumps({"response": json.dumps(inner_dict)}).encode("utf-8")

    def mock_urlopen(req, *args, **kwargs):
        if hasattr(req, "full_url") and "/api/tags" in req.full_url:
            class FakeTags:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return b'{"models": [{"name": "qwen2.5-coder:7b"}]}'
            return FakeTags()
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    payload = {
        "model_path": str(m_file),
        "view_path": str(v_file),
        "controller_path": str(c_file)
    }

    result = asyncio.run(post_ai_generate(payload))
    assert result["success"] is True

    m_content = m_file.read_text(encoding="utf-8")
    v_content = v_file.read_text(encoding="utf-8")
    c_content = c_file.read_text(encoding="utf-8")

    assert "def reset(self):" in m_content
    assert "AI-addition" in v_content
    assert "def handle_reset(self):" in c_content
