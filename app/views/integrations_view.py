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

"""Integration control page for external tools and MCP server lifecycle."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.controllers.integrations_controller import IntegrationsController
from app.models.mcp_server_manager import MCPServerManager


class IntegrationsView(QWidget):
    """Manage external MVC editor launch and MCP server settings/control."""

    def __init__(
        self,
        config: AppConfig,
        mcp_manager: MCPServerManager,
        controller: IntegrationsController | None = None,
        on_project_root_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._controller = controller or IntegrationsController(config, mcp_manager)
        self._on_project_root_changed = on_project_root_changed
        self._build_ui()
        self.sync_from_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        mvc_group = QGroupBox("MVC Editor Integration", self)
        mvc_layout = QVBoxLayout(mvc_group)
        mvc_form = QFormLayout()
        self.mvc_root_edit = QLineEdit(mvc_group)
        self.mvc_root_edit.setObjectName("mvcEditorRootEdit")
        self.mvc_root_edit.setReadOnly(True)
        mvc_form.addRow("Shared Library Root:", self.mvc_root_edit)
        mvc_layout.addLayout(mvc_form)

        mvc_buttons = QHBoxLayout()
        self.mvc_browse_button = QPushButton("Change Shared Root...", mvc_group)
        self.mvc_browse_button.setObjectName("mvcEditorBrowseButton")
        self.mvc_open_folder_button = QPushButton("Open Shared Root Folder", mvc_group)
        self.mvc_open_folder_button.setObjectName("mvcEditorOpenFolderButton")
        self.mvc_launch_button = QPushButton("Launch External MVC Editor", mvc_group)
        self.mvc_launch_button.setObjectName("mvcEditorLaunchButton")
        mvc_buttons.addWidget(self.mvc_browse_button)
        mvc_buttons.addWidget(self.mvc_open_folder_button)
        mvc_buttons.addWidget(self.mvc_launch_button)
        mvc_buttons.addStretch(1)
        mvc_layout.addLayout(mvc_buttons)

        mcp_group = QGroupBox("MCP Server Settings & Control", self)
        mcp_layout = QVBoxLayout(mcp_group)
        mcp_form = QFormLayout()
        self.mcp_host_edit = QLineEdit(mcp_group)
        self.mcp_host_edit.setObjectName("mcpHostEdit")
        self.mcp_port_spin = QSpinBox(mcp_group)
        self.mcp_port_spin.setObjectName("mcpPortSpin")
        self.mcp_port_spin.setRange(1, 65535)
        self.mcp_token_edit = QLineEdit(mcp_group)
        self.mcp_token_edit.setObjectName("mcpTokenEdit")
        self.mcp_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.mcp_autostart_check = QCheckBox("Auto-start MCP server with app", mcp_group)
        self.mcp_autostart_check.setObjectName("mcpAutoStartCheck")
        mcp_form.addRow("Host:", self.mcp_host_edit)
        mcp_form.addRow("Port:", self.mcp_port_spin)
        mcp_form.addRow("Token (optional):", self.mcp_token_edit)
        mcp_layout.addLayout(mcp_form)
        mcp_layout.addWidget(self.mcp_autostart_check)

        mcp_buttons = QHBoxLayout()
        self.mcp_save_button = QPushButton("Save MCP Settings", mcp_group)
        self.mcp_save_button.setObjectName("mcpSaveSettingsButton")
        self.mcp_start_button = QPushButton("Start MCP Server", mcp_group)
        self.mcp_start_button.setObjectName("mcpStartButton")
        self.mcp_stop_button = QPushButton("Stop MCP Server", mcp_group)
        self.mcp_stop_button.setObjectName("mcpStopButton")
        self.mcp_probe_button = QPushButton("Probe MCP Endpoint", mcp_group)
        self.mcp_probe_button.setObjectName("mcpProbeButton")
        mcp_buttons.addWidget(self.mcp_save_button)
        mcp_buttons.addWidget(self.mcp_start_button)
        mcp_buttons.addWidget(self.mcp_stop_button)
        mcp_buttons.addWidget(self.mcp_probe_button)
        mcp_buttons.addStretch(1)
        mcp_layout.addLayout(mcp_buttons)

        self.mcp_status_label = QLabel("MCP Status: stopped", mcp_group)
        self.mcp_status_label.setObjectName("mcpStatusLabel")
        mcp_layout.addWidget(self.mcp_status_label)

        root.addWidget(mvc_group)
        root.addWidget(mcp_group)
        root.addStretch(1)

        self.mvc_browse_button.clicked.connect(self._browse_mvc_root)
        self.mvc_open_folder_button.clicked.connect(self._open_mvc_folder)
        self.mvc_launch_button.clicked.connect(self._launch_mvc_editor)
        self.mcp_save_button.clicked.connect(self.save_settings)
        self.mcp_start_button.clicked.connect(self.start_mcp_server)
        self.mcp_stop_button.clicked.connect(self.stop_mcp_server)
        self.mcp_probe_button.clicked.connect(self.probe_mcp_server)

    def sync_from_config(self) -> None:
        """Refresh UI controls from current app config."""
        shared_root = self.config.project_root or ""
        self.mvc_root_edit.setText(shared_root)
        self.mcp_host_edit.setText((self.config.mcp_host or "127.0.0.1").strip() or "127.0.0.1")
        self.mcp_port_spin.setValue(int(self.config.mcp_port or 8765))
        self.mcp_token_edit.setText(self.config.mcp_auth_token or "")
        self.mcp_autostart_check.setChecked(bool(self.config.mcp_autostart))
        self.refresh_status()

    def save_settings(self) -> None:
        """Persist integration settings to config file."""
        root_changed = self._controller.save_settings(
            new_root=self.mvc_root_edit.text().strip(),
            host=self.mcp_host_edit.text().strip(),
            port=int(self.mcp_port_spin.value()),
            token=self.mcp_token_edit.text().strip(),
            autostart=self.mcp_autostart_check.isChecked()
        )
        if root_changed and self._on_project_root_changed is not None:
            self._on_project_root_changed(self.mvc_root_edit.text().strip())
        self.refresh_status("Integration settings saved.")

    def refresh_status(self, message: str | None = None) -> None:
        """Refresh MCP status label."""
        running = self._controller.is_mcp_running()
        endpoint = self._controller.mcp_endpoint()
        suffix = f" | {message}" if message else ""
        self.mcp_status_label.setText(f"MCP Status: {'running' if running else 'stopped'} @ {endpoint}{suffix}")

    def _browse_mvc_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Shared Library Root",
            self.mvc_root_edit.text(),
            QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.mvc_root_edit.setText(path)

    def _open_mvc_folder(self) -> None:
        ok, msg = self._controller.open_mvc_folder(self.mvc_root_edit.text())
        if not ok:
            QMessageBox.warning(self, "Invalid Path", msg)

    def _launch_mvc_editor(self) -> None:
        ok, msg = self._controller.launch_mvc_editor()
        if not ok:
            QMessageBox.warning(self, "Launch Failed", msg)

    def start_mcp_server(self) -> None:
        """Start MCP server using currently entered settings."""
        self.save_settings()
        ok, message = self._controller.start_mcp_server()
        level = QMessageBox.information if ok else QMessageBox.warning
        level(self, "MCP Server", message)
        self.refresh_status(message)

    def stop_mcp_server(self) -> None:
        """Stop MCP server."""
        ok, message = self._controller.stop_mcp_server()
        level = QMessageBox.information if ok else QMessageBox.warning
        level(self, "MCP Server", message)
        self.refresh_status(message)

    def probe_mcp_server(self) -> None:
        """Probe MCP endpoint and show response summary."""
        token = self.mcp_token_edit.text().strip()
        ok, message, data = self._controller.probe_mcp_server(token)
        
        if not ok:
            QMessageBox.warning(self, "Probe Failed", message)
            self.refresh_status(message)
            return

        import json
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit
        
        formatted = json.dumps(data, indent=2)
        
        dlg = QDialog(self)
        dlg.setWindowTitle("MCP Probe Success")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Successfully probed endpoint. Capabilities:"))
        text = QPlainTextEdit(dlg)
        text.setReadOnly(True)
        text.setPlainText(formatted)
        layout.addWidget(text)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.resize(400, 300)
        dlg.exec()
        self.refresh_status("Probe successful")
