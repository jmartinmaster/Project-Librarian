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
"""Smoke tests for integrations browser controls."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_manager import IndexManager
from app.models.mcp_server_manager import MCPServerManager
from app.views.integrations_view import IntegrationsView


def test_integrations_view_uses_stdlib_probe_client():
    source = Path("app/controllers/integrations_controller.py").read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "urllib.request" in source


def test_integrations_view_saves_settings(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsView(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    saved = {"count": 0}

    def fake_save(*args, **kwargs):
        saved["count"] += 1
        return False

    monkeypatch.setattr(widget._controller, "save_settings", fake_save)
    widget.mvc_root_edit.setText("C:/tools/MVC_editor")
    widget.mcp_host_edit.setText("127.0.0.1")
    widget.mcp_port_spin.setValue(9010)
    widget.mcp_token_edit.setText("abc123")
    widget.mcp_autostart_check.setChecked(True)

    widget.save_settings()

    assert saved["count"] == 1


def test_integrations_view_starts_and_stops_mcp(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsView(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget._controller, "start_mcp_server", lambda: (True, "started"))
    monkeypatch.setattr(widget._controller, "stop_mcp_server", lambda: (True, "stopped"))
    monkeypatch.setattr("app.views.integrations_view.QMessageBox.information", lambda *args, **kwargs: None)

    widget.start_mcp_server()
    assert "started" in widget.mcp_status_label.text()

    widget.stop_mcp_server()
    assert "stopped" in widget.mcp_status_label.text()


def test_integrations_view_probe_success(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsView(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget._controller, "probe_mcp_server", lambda token: (True, "Probe OK", {"status": "ok"}))
    monkeypatch.setattr("PyQt6.QtWidgets.QDialog.exec", lambda *args, **kwargs: None)

    widget.probe_mcp_server()
    assert "Probe successful" in widget.mcp_status_label.text()


def test_integrations_view_probe_http_error(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    widget = IntegrationsView(config=manager.config, mcp_manager=mcp_manager)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget._controller, "probe_mcp_server", lambda token: (False, "Probe failed (401)", None))
    monkeypatch.setattr("app.views.integrations_view.QMessageBox.warning", lambda *args, **kwargs: None)

    widget.probe_mcp_server()
    assert "Probe failed (401)" in widget.mcp_status_label.text()


def test_integrations_view_notifies_on_project_root_change(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    mcp_manager = MCPServerManager(index_manager=manager)
    callback = {"root": ""}

    def on_root_changed(new_root: str) -> None:
        callback["root"] = new_root

    widget = IntegrationsView(config=manager.config, mcp_manager=mcp_manager, on_project_root_changed=on_root_changed)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget._controller, "save_settings", lambda *args, **kwargs: True)
    widget.mvc_root_edit.setText("C:/repo/new-root")
    widget.save_settings()

    assert callback["root"] == "C:/repo/new-root"
