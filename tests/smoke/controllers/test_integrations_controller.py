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
"""Smoke tests for IntegrationsController."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from app.controllers.integrations_controller import IntegrationsController
from app.models.mcp_server_manager import MCPServerManager


def test_integrations_controller_save_settings(app_config):
    manager = MCPServerManager(app_config)
    controller = IntegrationsController(config=app_config, mcp_manager=manager)

    root_changed = controller.save_settings(
        new_root="/new/root",
        host="0.0.0.0",
        port=1234,
        token="secret",
        autostart=True,
    )
    
    assert root_changed is True
    assert app_config.project_root == "/new/root"
    assert app_config.mvc_editor_root == "/new/root"
    assert app_config.mcp_host == "0.0.0.0"
    assert app_config.mcp_port == 1234
    assert app_config.mcp_auth_token == "secret"
    assert app_config.mcp_autostart is True


def test_integrations_controller_mcp_lifecycle(app_config, monkeypatch):
    manager = MCPServerManager(app_config)
    controller = IntegrationsController(config=app_config, mcp_manager=manager)

    monkeypatch.setattr(manager, "is_running", lambda: True)
    monkeypatch.setattr(manager, "endpoint", lambda: "http://127.0.0.1:8765")
    monkeypatch.setattr(manager, "start", lambda: (True, "Started"))
    monkeypatch.setattr(manager, "stop", lambda: (True, "Stopped"))

    assert controller.is_mcp_running() is True
    assert controller.mcp_endpoint() == "http://127.0.0.1:8765"
    assert controller.start_mcp_server() == (True, "Started")
    assert controller.stop_mcp_server() == (True, "Stopped")


def test_mcp_server_manager_env_flags(app_config, monkeypatch):
    mock_index_mgr = Mock()
    mock_index_mgr.config = app_config
    manager = MCPServerManager(mock_index_mgr)
    captured_env = {}

    def fake_popen(cmd, cwd, env, **kwargs):
        nonlocal captured_env
        captured_env = env
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        return mock_proc

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    ok, msg = manager.start()
    assert ok is True
    assert captured_env.get("THE_LIBRARIAN_IS_CHILD") == "1"
    assert captured_env.get("THE_LIBRARIAN_NO_SUPERVISOR") == "1"
    assert captured_env.get("THE_LIBRARIAN_MCP_SERVER") == "1"


def test_integrations_controller_launch_mvc_editor(app_config, monkeypatch, tmp_path):
    manager = MCPServerManager(app_config)
    controller = IntegrationsController(config=app_config, mcp_manager=manager)
    
    # Set up a fake mvc editor root
    mvc_root = tmp_path / "mvc_editor"
    mvc_root.mkdir()
    (mvc_root / "main.py").touch()
    
    app_config.mvc_editor_root = str(mvc_root)
    
    called_popen = False
    def fake_popen(*args, **kwargs):
        nonlocal called_popen
        called_popen = True
        return Mock()
        
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    
    ok, msg = controller.launch_mvc_editor()
    assert ok is True
    assert called_popen is True


def test_integrations_controller_probe_mcp_server(app_config, monkeypatch):
    manager = MCPServerManager(app_config)
    controller = IntegrationsController(config=app_config, mcp_manager=manager)
    
    monkeypatch.setattr(manager, "endpoint", lambda: "http://127.0.0.1:8765")
    
    class FakeResponse:
        status = 200
        def read(self):
            return json.dumps({"capabilities": ["test"]}).encode("utf-8")
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def fake_urlopen(*args, **kwargs):
        return FakeResponse()
        
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    
    ok, msg, data = controller.probe_mcp_server("token")
    assert ok is True
    assert data == {"capabilities": ["test"]}
