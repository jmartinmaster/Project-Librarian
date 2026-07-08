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

"""Smoke tests for integrations browser controls."""

from __future__ import annotations

import io
import urllib.error
from pathlib import Path

from app.indexer.index_manager import IndexManager
from app.services.mcp_server_manager import MCPServerManager
from app.ui.integrations_browser import IntegrationsBrowser


def test_integrations_browser_uses_stdlib_probe_client():
    source = Path("app/ui/integrations_browser.py").read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "urllib.request" in source


def test_integrations_browser_saves_settings(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    saved = {"count": 0}

    def fake_save(config):
        saved["count"] += 1
        return None

    monkeypatch.setattr("app.ui.integrations_browser.save_config", fake_save)
    widget.mvc_root_edit.setText("C:/tools/MVC_editor")
    widget.mcp_host_edit.setText("127.0.0.1")
    widget.mcp_port_spin.setValue(9010)
    widget.mcp_token_edit.setText("abc123")
    widget.mcp_autostart_check.setChecked(True)

    widget.save_settings()

    assert saved["count"] == 1
    assert manager.config.project_root == "C:/tools/MVC_editor"
    assert manager.config.mvc_editor_root == "C:/tools/MVC_editor"
    assert manager.config.mcp_port == 9010
    assert manager.config.mcp_auth_token == "abc123"
    assert manager.config.mcp_autostart is True


def test_integrations_browser_starts_and_stops_mcp(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget.mcp_manager, "start", lambda: (True, "started"))
    monkeypatch.setattr(widget.mcp_manager, "stop", lambda: (True, "stopped"))
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.information", lambda *args, **kwargs: None)

    widget.start_mcp_server()
    assert "started" in widget.mcp_status_label.text()

    widget.stop_mcp_server()
    assert "stopped" in widget.mcp_status_label.text()


def test_integrations_browser_probe_success(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            return b'{"status":"ok"}'

    monkeypatch.setattr("app.ui.integrations_browser.urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.information", lambda *args, **kwargs: None)

    widget.probe_mcp_server()
    assert "Probe OK" in widget.mcp_status_label.text()


def test_integrations_browser_probe_http_error(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    def fake_urlopen(*args, **kwargs):
        raise urllib.error.HTTPError(url="http://localhost", code=401, msg="Unauthorized", hdrs=None, fp=io.BytesIO())

    monkeypatch.setattr("app.ui.integrations_browser.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.warning", lambda *args, **kwargs: None)

    widget.probe_mcp_server()
    assert "Probe failed (401)" in widget.mcp_status_label.text()


def test_integrations_browser_notifies_on_project_root_change(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    callback = {"root": ""}

    def on_root_changed(new_root: str) -> None:
        callback["root"] = new_root

    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager, on_project_root_changed=on_root_changed)
    qtbot.addWidget(widget)

    monkeypatch.setattr("app.ui.integrations_browser.save_config", lambda *_args, **_kwargs: None)
    widget.mvc_root_edit.setText("C:/repo/new-root")
    widget.save_settings()

    assert callback["root"] == "C:/repo/new-root"
