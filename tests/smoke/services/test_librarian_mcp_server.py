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

"""Smoke tests for the standalone MCP-compatible server runtime."""

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

        # Test definition endpoint (GET)
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/definition?q=ping",
            timeout=2.0,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert isinstance(payload.get("count"), int)
        assert isinstance(payload.get("results"), list)

        # Test diagnostics endpoint (GET)
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/diagnostics",
            timeout=2.0,
        ) as response:
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
