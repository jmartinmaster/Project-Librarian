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
    source = Path("app/controllers/integrations_controller.py").read_text(encoding="utf-8")
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

    monkeypatch.setattr("app.controllers.integrations_controller.save_config", fake_save)
    widget.mcp_host_edit.setText("127.0.0.1")
    widget.mcp_port_spin.setValue(9010)
    widget.mcp_token_edit.setText("abc123")
    widget.mcp_autostart_check.setChecked(True)

    widget.save_settings()

    assert saved["count"] == 1
    assert manager.config.mcp_port == 9010
    assert manager.config.mcp_auth_token == "abc123"
    assert manager.config.mcp_autostart is True


def test_integrations_browser_starts_and_stops_mcp(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget._controller.mcp_manager, "start", lambda: (True, "started"))
    monkeypatch.setattr(widget._controller.mcp_manager, "stop", lambda: (True, "stopped"))
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.information", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.controllers.integrations_controller.save_config", lambda *args, **kwargs: None)

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

    monkeypatch.setattr("app.controllers.integrations_controller.urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
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

    monkeypatch.setattr("app.controllers.integrations_controller.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.warning", lambda *args, **kwargs: None)

    widget.probe_mcp_server()
    assert "Probe failed" in widget.mcp_status_label.text()


def test_integrations_browser_search_via_mcp(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    class FakeSearchResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            return False
        def read(self):
            return b'{"results": [{"path": "dummy.py", "file_type": "py", "preview": "print(123)", "score": 80}]}'

    monkeypatch.setattr("app.controllers.integrations_controller.urllib.request.urlopen", lambda *args, **kwargs: FakeSearchResponse())
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.warning", lambda *args, **kwargs: None)

    widget.mcp_search_input.setText("dummy")
    widget.search_via_mcp()

    assert widget.mcp_explorer_tree.topLevelItemCount() == 1
    item = widget.mcp_explorer_tree.topLevelItem(0)
    assert item.text(0) == "dummy.py"
    assert item.text(1) == "file (py)"
    assert item.text(2) == "print(123)"


def test_integrations_browser_load_ast(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsBrowser(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTreeWidgetItem
    item = QTreeWidgetItem(widget.mcp_explorer_tree, ["dummy.py", "file (py)", "print(123)"])
    item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "file", "path": "dummy.py"})
    widget.mcp_explorer_tree.setCurrentItem(item)

    class FakeASTResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            return False
        def read(self):
            return b'{"language": "python", "classes": [{"name": "MyClass", "methods": [{"signature": "my_method()", "docstring": "hello"}], "docstring": ""}], "functions": [], "variables": [], "imports": []}'

    monkeypatch.setattr("app.controllers.integrations_controller.urllib.request.urlopen", lambda *args, **kwargs: FakeASTResponse())
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.ui.integrations_browser.QMessageBox.information", lambda *args, **kwargs: None)

    widget.load_selected_ast()

    assert item.childCount() == 1
    classes_root = item.child(0)
    assert classes_root.text(0) == "Classes"
    assert classes_root.childCount() == 1
    class_item = classes_root.child(0)
    assert class_item.text(0) == "MyClass"
    assert class_item.childCount() == 1
    method_item = class_item.child(0)
    assert method_item.text(0) == "my_method()"

