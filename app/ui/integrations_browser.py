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

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
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

from app.config import AppConfig, save_config
from app.services.mcp_server_manager import MCPServerManager

DEFAULT_MVC_EDITOR_PATH = Path(r"C:\Users\jamie\OneDrive\Personel\Documents\GitHub\MVC_editor")


class IntegrationsBrowser(QWidget):
    """Manage external MVC editor launch and MCP server settings/control."""

    def __init__(
        self,
        config: AppConfig,
        mcp_manager: MCPServerManager,
        on_project_root_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.mcp_manager = mcp_manager
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
        shared_root = str(Path(self.config.project_root or Path.cwd()).resolve())
        self.mvc_root_edit.setText(shared_root)
        self.mcp_host_edit.setText((self.config.mcp_host or "127.0.0.1").strip() or "127.0.0.1")
        self.mcp_port_spin.setValue(int(self.config.mcp_port or 8765))
        self.mcp_token_edit.setText(self.config.mcp_auth_token or "")
        self.mcp_autostart_check.setChecked(bool(self.config.mcp_autostart))
        self.refresh_status()

    def save_settings(self) -> None:
        """Persist integration settings to config file."""
        new_root = self.mvc_root_edit.text().strip()
        previous_root = str(Path(self.config.project_root or Path.cwd()).resolve())
        self.config.project_root = new_root
        self.config.mvc_editor_root = new_root
        self.config.mcp_host = self.mcp_host_edit.text().strip() or "127.0.0.1"
        self.config.mcp_port = int(self.mcp_port_spin.value())
        self.config.mcp_auth_token = self.mcp_token_edit.text().strip()
        self.config.mcp_transport = "streamable-http"
        self.config.mcp_autostart = self.mcp_autostart_check.isChecked()
        save_config(self.config)
        if self._on_project_root_changed is not None and new_root and new_root != previous_root:
            self._on_project_root_changed(new_root)
        self.refresh_status("Integration settings saved.")

    def refresh_status(self, message: str | None = None) -> None:
        """Refresh MCP status label."""
        running = self.mcp_manager.is_running()
        endpoint = self.mcp_manager.endpoint()
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
        path = Path(self.mvc_root_edit.text().strip())
        if not path.exists():
            QMessageBox.warning(self, "Invalid Path", "MVC Editor root does not exist.")
            return
        if sys.platform == "win32":
            subprocess.run(["explorer", str(path)], check=False, capture_output=True)  # noqa: S603
            return
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.run([opener, str(path)], check=False, capture_output=True)  # noqa: S603

    def _launch_mvc_editor(self) -> None:
        path = Path((self.config.mvc_editor_root or "").strip())
        if not path:
            if DEFAULT_MVC_EDITOR_PATH.exists():
                path = DEFAULT_MVC_EDITOR_PATH
            else:
                QMessageBox.warning(self, "External Editor Missing", "External MVC editor path is not configured.")
                return
        entrypoint = path / "main.py"
        if not entrypoint.exists():
            QMessageBox.warning(self, "Missing Entry Point", f"Could not find {entrypoint}.")
            return
        venv_python = path / ".venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(  # noqa: S603 - local trusted command
            [python_exe, str(entrypoint)],
            cwd=str(Path(self.config.project_root or Path.cwd()).resolve()),
            creationflags=creationflags,
        )
        self.config.mvc_editor_root = str(path.resolve())
        save_config(self.config)

    def start_mcp_server(self) -> None:
        """Start MCP server using currently entered settings."""
        self.save_settings()
        ok, message = self.mcp_manager.start()
        level = QMessageBox.information if ok else QMessageBox.warning
        level(self, "MCP Server", message)
        self.refresh_status(message)

    def stop_mcp_server(self) -> None:
        """Stop MCP server."""
        ok, message = self.mcp_manager.stop()
        level = QMessageBox.information if ok else QMessageBox.warning
        level(self, "MCP Server", message)
        self.refresh_status(message)

    def probe_mcp_server(self) -> None:
        """Probe MCP endpoint and show response summary."""
        endpoint = self.mcp_manager.endpoint()
        headers: dict[str, str] = {}
        token = self.mcp_token_edit.text().strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(endpoint, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                status_code = int(getattr(response, "status", 200))
                response_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            QMessageBox.warning(self, "Probe Failed", f"Probe returned HTTP {exc.code}")
            self.refresh_status(f"Probe failed ({exc.code})")
            return
        except urllib.error.URLError as exc:
            QMessageBox.warning(self, "Probe Failed", f"Could not reach MCP endpoint:\n{exc}")
            self.refresh_status("Probe failed (connection)")
            return

        if status_code != 200:
            QMessageBox.warning(self, "Probe Failed", f"Probe returned HTTP {status_code}")
            self.refresh_status(f"Probe failed ({status_code})")
            return

        try:
            payload = json.loads(response_body)
        except ValueError:
            QMessageBox.warning(self, "Probe Failed", "Probe returned non-JSON response.")
            self.refresh_status("Probe failed (invalid payload)")
            return

        status_text = str(payload.get("status", "ok"))
        QMessageBox.information(self, "Probe Success", f"MCP probe status: {status_text}")
        self.refresh_status(f"Probe OK ({status_text})")
