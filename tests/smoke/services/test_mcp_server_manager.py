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
"""Smoke tests for MCP server process manager behavior."""

from __future__ import annotations

import subprocess

from app.indexer.index_manager import IndexManager
from app.models.mcp_server_manager import MCPServerManager


def test_mcp_manager_builds_command_with_token(app_config):
    manager = IndexManager(app_config)
    manager.config.mcp_host = "127.0.0.1"
    manager.config.mcp_port = 9988
    manager.config.mcp_auth_token = "secret-token"

    mcp_manager = MCPServerManager(index_manager=manager)
    command = mcp_manager._build_command()

    assert "app.models.librarian_mcp_server" in command
    assert "--host" in command and "127.0.0.1" in command
    assert "--port" in command and "9988" in command
    assert "--token" in command and "secret-token" in command


def test_mcp_manager_endpoint_uses_config(app_config):
    manager = IndexManager(app_config)
    manager.config.mcp_host = "localhost"
    manager.config.mcp_port = 8765
    mcp_manager = MCPServerManager(index_manager=manager)

    assert mcp_manager.endpoint() == "http://localhost:8765/api/mcp-probe"


def test_mcp_manager_start_and_stop_flow(monkeypatch, app_config):
    manager = IndexManager(app_config)
    manager.config.project_root = app_config.project_root

    class FakeProcess:
        def __init__(self):
            self.running = True
            self.terminated = False
            self.killed = False

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.terminated = True
            self.running = False

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True
            self.running = False

    fake_process = FakeProcess()
    monkeypatch.setattr("app.models.mcp_server_manager.subprocess.Popen", lambda *args, **kwargs: fake_process)

    mcp_manager = MCPServerManager(index_manager=manager)
    started, start_message = mcp_manager.start()
    assert started is True
    assert "started at" in start_message
    assert mcp_manager.is_running() is True

    started_again, already_running_message = mcp_manager.start()
    assert started_again is False
    assert "already running" in already_running_message.lower()

    stopped, stop_message = mcp_manager.stop()
    assert stopped is True
    assert "stopped" in stop_message.lower()
    assert fake_process.terminated is True
    assert mcp_manager.is_running() is False


def test_mcp_manager_stop_kills_when_terminate_timeout(monkeypatch, app_config):
    manager = IndexManager(app_config)
    manager.config.project_root = app_config.project_root

    class FakeProcess:
        def __init__(self):
            self.running = True
            self.killed = False

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            return None

        def wait(self, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired(cmd="fake", timeout=float(timeout or 0))
            self.running = False
            return 0

        def kill(self):
            self.killed = True

    fake_process = FakeProcess()
    monkeypatch.setattr("app.models.mcp_server_manager.subprocess.Popen", lambda *args, **kwargs: fake_process)

    mcp_manager = MCPServerManager(index_manager=manager)
    mcp_manager.start()
    stopped, _ = mcp_manager.stop()
    assert stopped is True
    assert fake_process.killed is True


def test_mcp_manager_start_uses_app_root_and_pythonpath(monkeypatch, app_config):
    manager = IndexManager(app_config)
    manager.config.project_root = app_config.project_root

    captured_cwd = None
    captured_env = None

    class FakeProcess:
        def poll(self):
            return None

    def fake_popen(command, cwd=None, env=None, **kwargs):
        nonlocal captured_cwd, captured_env
        captured_cwd = cwd
        captured_env = env
        return FakeProcess()

    monkeypatch.setattr("app.models.mcp_server_manager.subprocess.Popen", fake_popen)

    mcp_manager = MCPServerManager(index_manager=manager)
    mcp_manager.start()

    from pathlib import Path
    expected_app_root = str(Path(__file__).resolve().parents[3])
    assert captured_cwd is not None
    assert Path(captured_cwd).resolve() == Path(expected_app_root).resolve()
    assert captured_env is not None
    assert "PYTHONPATH" in captured_env
    assert expected_app_root in captured_env["PYTHONPATH"]

