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
"""Integration control page for external tools and MCP server lifecycle."""

from __future__ import annotations

import json
import re
import urllib.request
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
    QScrollArea,
    QFrame,
    QComboBox,
    QTreeWidget,
    QTreeWidgetItem,
)

from app.config import AppConfig, save_config
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll_area)

        container = QWidget()
        scroll_area.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        mvc_group = QGroupBox("MVC Editor Integration", container)
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

        mcp_group = QGroupBox("MCP Server Settings & Control", container)
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

        ai_group = QGroupBox("Local AI Settings (Ollama)", container)
        ai_layout = QVBoxLayout(ai_group)
        ai_form = QFormLayout()
        self.ai_url_edit = QLineEdit(ai_group)
        self.ai_url_edit.setObjectName("aiUrlEdit")
        self.ai_model_edit = QComboBox(ai_group)
        self.ai_model_edit.setEditable(True)
        self.ai_model_edit.setObjectName("aiModelEdit")
        ai_form.addRow("Ollama API URL:", self.ai_url_edit)
        ai_form.addRow("Ollama Model Name:", self.ai_model_edit)
        ai_layout.addLayout(ai_form)

        self.ai_boilerplate_only_check = QCheckBox("Generate stubs/boilerplates only (no full logic implementation)", ai_group)
        self.ai_boilerplate_only_check.setObjectName("aiBoilerplateOnlyCheck")
        ai_layout.addWidget(self.ai_boilerplate_only_check)

        # MicroPython Hardware Integration Group
        from PyQt6.QtWidgets import QPlainTextEdit
        from app.controllers.micropython_controller import MicroPythonController
        self._mcu_controller = MicroPythonController(self.config)

        mcu_group = QGroupBox("MicroPython Device & Hardware Testing", container)
        mcu_layout = QVBoxLayout(mcu_group)

        # Safety Guard Checkbox
        self.mcu_live_code_check = QCheckBox("⚡ Enable Live Code Execution on Hardware (Safety Guard)", mcu_group)
        self.mcu_live_code_check.setObjectName("mcuLiveCodeCheck")
        self.mcu_live_code_check.setStyleSheet("font-weight: bold; color: #bc4c00;")
        self.mcu_live_code_check.setToolTip("Must be checked to permit sending, flashing, or running code on physical hardware.")
        mcu_layout.addWidget(self.mcu_live_code_check)

        mcu_form = QFormLayout()
        mcu_port_row = QHBoxLayout()
        self.mcu_port_combo = QComboBox(mcu_group)
        self.mcu_port_combo.setObjectName("mcuPortCombo")
        self.mcu_port_combo.setEditable(True)
        self.mcu_scan_ports_btn = QPushButton("Scan Ports", mcu_group)
        self.mcu_scan_ports_btn.setObjectName("mcuScanPortsBtn")
        mcu_port_row.addWidget(self.mcu_port_combo, 1)
        mcu_port_row.addWidget(self.mcu_scan_ports_btn)
        mcu_form.addRow("Device Port:", mcu_port_row)

        self.mcu_runner_edit = QLineEdit(mcu_group)
        self.mcu_runner_edit.setObjectName("mcuRunnerEdit")
        self.mcu_runner_edit.setPlaceholderText("mpremote")
        mcu_form.addRow("Runner Command:", self.mcu_runner_edit)
        mcu_layout.addLayout(mcu_form)

        mcu_buttons = QHBoxLayout()
        self.mcu_info_btn = QPushButton("Get Device Info", mcu_group)
        self.mcu_info_btn.setObjectName("mcuInfoBtn")
        self.mcu_upload_debug_btn = QPushButton("🚀 Upload & Debug (Watch Startup)", mcu_group)
        self.mcu_upload_debug_btn.setObjectName("mcuUploadDebugBtn")
        self.mcu_run_file_btn = QPushButton("Run Local File...", mcu_group)
        self.mcu_run_file_btn.setObjectName("mcuRunFileBtn")
        self.mcu_upload_btn = QPushButton("Upload File...", mcu_group)
        self.mcu_upload_btn.setObjectName("mcuUploadBtn")
        self.mcu_reset_btn = QPushButton("Soft Reset", mcu_group)
        self.mcu_reset_btn.setObjectName("mcuResetBtn")
        self.mcu_stop_repl_btn = QPushButton("Stop REPL", mcu_group)
        self.mcu_stop_repl_btn.setObjectName("mcuStopReplBtn")

        mcu_buttons.addWidget(self.mcu_info_btn)
        mcu_buttons.addWidget(self.mcu_upload_debug_btn)
        mcu_buttons.addWidget(self.mcu_run_file_btn)
        mcu_buttons.addWidget(self.mcu_upload_btn)
        mcu_buttons.addWidget(self.mcu_reset_btn)
        mcu_buttons.addWidget(self.mcu_stop_repl_btn)
        mcu_buttons.addStretch(1)
        mcu_layout.addLayout(mcu_buttons)

        mcu_log_header = QHBoxLayout()
        mcu_log_header.addWidget(QLabel("Device REPL & Startup Monitor:", mcu_group))
        mcu_log_header.addStretch(1)
        self.mcu_clear_log_btn = QPushButton("Clear Monitor", mcu_group)
        self.mcu_clear_log_btn.setObjectName("mcuClearLogBtn")
        mcu_log_header.addWidget(self.mcu_clear_log_btn)
        mcu_layout.addLayout(mcu_log_header)

        self.mcu_output_text = QPlainTextEdit(mcu_group)
        self.mcu_output_text.setObjectName("mcuOutputText")
        self.mcu_output_text.setReadOnly(True)
        self.mcu_output_text.setMinimumHeight(140)
        self.mcu_output_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #11111b;
                color: #a6e3a1;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #313244;
                border-radius: 4px;
            }
        """)
        # On-Device Filesystem & Flash Browser
        mcu_fs_header = QHBoxLayout()
        mcu_fs_header.addWidget(QLabel("On-Device Flash Filesystem:", mcu_group))
        mcu_fs_header.addStretch(1)

        self.mcu_refresh_fs_btn = QPushButton("Refresh Device Files", mcu_group)
        self.mcu_refresh_fs_btn.setObjectName("mcuRefreshFsBtn")
        self.mcu_download_fs_btn = QPushButton("Download Selected", mcu_group)
        self.mcu_download_fs_btn.setObjectName("mcuDownloadFsBtn")
        self.mcu_delete_fs_btn = QPushButton("Delete Selected", mcu_group)
        self.mcu_delete_fs_btn.setObjectName("mcuDeleteFsBtn")

        mcu_fs_header.addWidget(self.mcu_refresh_fs_btn)
        mcu_fs_header.addWidget(self.mcu_download_fs_btn)
        mcu_fs_header.addWidget(self.mcu_delete_fs_btn)
        mcu_layout.addLayout(mcu_fs_header)

        self.mcu_fs_tree = QTreeWidget(mcu_group)
        self.mcu_fs_tree.setObjectName("mcuFsTree")
        self.mcu_fs_tree.setHeaderLabels(["Remote Path", "Size", "Type"])
        self.mcu_fs_tree.setMinimumHeight(100)
        mcu_layout.addWidget(self.mcu_fs_tree)

        mcu_layout.addWidget(self.mcu_output_text)

        # Live REPL interactive input row
        repl_input_layout = QHBoxLayout()
        self.mcu_input_edit = QLineEdit(mcu_group)
        self.mcu_input_edit.setObjectName("mcuInputEdit")
        self.mcu_input_edit.setPlaceholderText("Type command / input to send to live REPL or device (press Enter)...")
        self.mcu_input_edit.setStyleSheet("""
            QLineEdit {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
            }
        """)
        self.mcu_send_btn = QPushButton("Send Input", mcu_group)
        self.mcu_send_btn.setObjectName("mcuSendBtn")
        self.mcu_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
        """)
        repl_input_layout.addWidget(self.mcu_input_edit)
        repl_input_layout.addWidget(self.mcu_send_btn)
        mcu_layout.addLayout(repl_input_layout)

        root.addWidget(mvc_group)
        root.addWidget(mcp_group)
        root.addWidget(ai_group)
        root.addWidget(mcu_group)
        root.addStretch(1)

        self.mvc_browse_button.clicked.connect(self._browse_mvc_root)
        self.mvc_open_folder_button.clicked.connect(self._open_mvc_folder)
        self.mvc_launch_button.clicked.connect(self._launch_mvc_editor)
        self.mcp_save_button.clicked.connect(self.save_settings)
        self.mcp_start_button.clicked.connect(self.start_mcp_server)
        self.mcp_stop_button.clicked.connect(self.stop_mcp_server)
        self.mcp_probe_button.clicked.connect(self.probe_mcp_server)

        # MicroPython signals
        self.mcu_live_code_check.toggled.connect(self._on_mcu_live_code_toggled)
        self.mcu_scan_ports_btn.clicked.connect(self._scan_mcu_ports)
        self.mcu_info_btn.clicked.connect(self._on_mcu_get_info)
        self.mcu_upload_debug_btn.clicked.connect(self._on_mcu_upload_and_debug)
        self.mcu_run_file_btn.clicked.connect(self._on_mcu_run_file)
        self.mcu_upload_btn.clicked.connect(self._on_mcu_upload_file)
        self.mcu_reset_btn.clicked.connect(self._on_mcu_soft_reset)
        self.mcu_stop_repl_btn.clicked.connect(self._on_mcu_stop_repl)
        self.mcu_clear_log_btn.clicked.connect(self.mcu_output_text.clear)
        self.mcu_send_btn.clicked.connect(self._on_mcu_send_input)
        self.mcu_input_edit.returnPressed.connect(self._on_mcu_send_input)
        self.mcu_refresh_fs_btn.clicked.connect(self._on_mcu_refresh_files)
        self.mcu_download_fs_btn.clicked.connect(self._on_mcu_download_file)
        self.mcu_delete_fs_btn.clicked.connect(self._on_mcu_delete_file)

        self._scan_mcu_ports()
        self._update_mcu_buttons_state()

    def _poll_local_models(self) -> list[str]:
        """Query local Ollama tags endpoint to discover available models."""
        url = self.ai_url_edit.text().strip() or "http://127.0.0.1:11434"
        match = re.match(r"(https?://[^/]+)", url)
        host = match.group(1) if match else "http://127.0.0.1:11434"
        if "localhost" in host:
            host = host.replace("localhost", "127.0.0.1")
        
        try:
            req = urllib.request.Request(f"{host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return [m["name"] for m in payload.get("models", [])]
        except Exception:
            return []

    def sync_from_config(self) -> None:
        """Refresh UI controls from current app config."""
        shared_root = self.config.project_root or ""
        self.mvc_root_edit.setText(shared_root)
        self.mcp_host_edit.setText((self.config.mcp_host or "127.0.0.1").strip() or "127.0.0.1")
        self.mcp_port_spin.setValue(int(self.config.mcp_port or 8765))
        self.mcp_token_edit.setText(self.config.mcp_auth_token or "")
        self.mcp_autostart_check.setChecked(bool(self.config.mcp_autostart))
        self.ai_url_edit.setText(self.config.ai_url or "http://localhost:11434/api/generate")
        self.ai_boilerplate_only_check.setChecked(bool(getattr(self.config, "ai_boilerplate_only", False)))
        
        # Poll local models
        models = self._poll_local_models()
        self.ai_model_edit.clear()
        if models:
            self.ai_model_edit.addItems(models)
            
        current_model = self.config.ai_model or "qwen2.5-coder:14b"
        self.ai_model_edit.setEditText(current_model)
        
        # Sync MicroPython controls
        self.mcu_live_code_check.setChecked(bool(getattr(self.config, "micropython_live_code", False)))
        self.mcu_runner_edit.setText(getattr(self.config, "micropython_runner_cmd", "mpremote") or "mpremote")
        self._update_mcu_buttons_state()
        
        self.refresh_status()

    def save_settings(self) -> None:
        """Persist integration settings to config file."""
        root_changed = self._controller.save_settings(
            new_root=self.mvc_root_edit.text().strip(),
            host=self.mcp_host_edit.text().strip(),
            port=int(self.mcp_port_spin.value()),
            token=self.mcp_token_edit.text().strip(),
            autostart=self.mcp_autostart_check.isChecked(),
            ai_url=self.ai_url_edit.text().strip(),
            ai_model=self.ai_model_edit.currentText().strip(),
            ai_boilerplate_only=self.ai_boilerplate_only_check.isChecked(),
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
            self.config.project_root = path
            self.config.mvc_editor_root = path
            save_config(self.config)
            if self._on_project_root_changed is not None:
                self._on_project_root_changed(path)

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

    # --- MicroPython Device Methods ---

    def _on_mcu_live_code_toggled(self, checked: bool) -> None:
        """Handle toggle of live code safety checkbox."""
        self.config.micropython_live_code = checked
        self._mcu_controller.set_live_code_enabled(checked)
        save_config(self.config)
        self._update_mcu_buttons_state()
        status_msg = "Live Code ENABLED (Hardware execution permitted)" if checked else "Live Code DISABLED (Safety guard active)"
        self._append_mcu_log(f"[{status_msg}]\n")

    def _update_mcu_buttons_state(self) -> None:
        """Enable or disable hardware action buttons based on Live Code safety guard."""
        enabled = self.mcu_live_code_check.isChecked()
        self.mcu_info_btn.setEnabled(enabled)
        self.mcu_upload_debug_btn.setEnabled(enabled)
        self.mcu_run_file_btn.setEnabled(enabled)
        self.mcu_upload_btn.setEnabled(enabled)
        self.mcu_reset_btn.setEnabled(enabled)
        self.mcu_stop_repl_btn.setEnabled(enabled)

    def _scan_mcu_ports(self) -> None:
        """Scan and populate available serial ports in combo box."""
        current_text = self.mcu_port_combo.currentText().strip() or getattr(self.config, "micropython_port", "auto")
        self.mcu_port_combo.clear()
        ports = self._mcu_controller.list_ports()
        for p in ports:
            self.mcu_port_combo.addItem(f"{p['port']} ({p['description']})", p["port"])
        
        # Select matching or default
        index = self.mcu_port_combo.findData(current_text)
        if index >= 0:
            self.mcu_port_combo.setCurrentIndex(index)
        else:
            self.mcu_port_combo.setEditText(current_text)

    def _selected_mcu_port(self) -> str:
        """Return currently selected or typed port string."""
        selected_data = self.mcu_port_combo.currentData()
        if selected_data:
            return str(selected_data).strip()
        text = self.mcu_port_combo.currentText().strip()
        if " (" in text:
            text = text.split(" (", 1)[0].strip()
        return text or "auto"

    def _append_mcu_log(self, text: str) -> None:
        """Append log text to the device terminal output window."""
        self.mcu_output_text.appendPlainText(text.rstrip("\n"))
        scrollbar = self.mcu_output_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _on_mcu_send_input(self) -> None:
        """Send line of input to the live streaming REPL process."""
        text = self.mcu_input_edit.text()
        if not text:
            return
        self.mcu_input_edit.clear()
        self._append_mcu_log(f">>> {text}")
        ok = self._mcu_controller.send_repl_input(text)
        if not ok:
            self._append_mcu_log("[Input not delivered: No active live REPL session]\n")

    def _handle_permission_error(self, port: str, error_detail: str) -> bool:
        """Prompt user with SudoAuthDialog to fix permissions. Return True if resolved."""
        from app.views.sudo_dialog import SudoAuthDialog
        dlg = SudoAuthDialog(port=port, error_detail=error_detail, parent=self)
        if dlg.exec() == SudoAuthDialog.DialogCode.Accepted:
            password = dlg.get_password()
            if dlg.should_fix_port_permissions():
                self._append_mcu_log(f"\n[Attempting to fix permissions on {port} with sudo...]")
                ok, msg = self._mcu_controller.fix_port_permissions(port, password)
                self._append_mcu_log(f"[{msg}]\n")
                return ok
        return False

    def _on_mcu_get_info(self) -> None:
        """Query microcontroller device information."""
        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n[Querying device on port '{port}'...]")
        ok, info = self._mcu_controller.get_device_info(port=port)
        if not ok and self._mcu_controller.is_permission_error(info.get("error", "")):
            if self._handle_permission_error(port, info.get("error", "")):
                ok, info = self._mcu_controller.get_device_info(port=port)
        formatted = self._mcu_controller.format_device_info(info)
        self._append_mcu_log(formatted + "\n")

    def _on_mcu_run_file(self) -> None:
        """Prompt for a local file and execute it on the microcontroller."""
        initial_dir = self.config.project_root or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python File to Run on MCU",
            initial_dir,
            "Python Files (*.py);;All Files (*)",
        )
        if not file_path:
            return
        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n[Executing '{Path(file_path).name}' on MCU port '{port}'...]")
        ok, output = self._mcu_controller.run_file(file_path, port=port)
        if not ok and self._mcu_controller.is_permission_error(output):
            if self._handle_permission_error(port, output):
                ok, output = self._mcu_controller.run_file(file_path, port=port)
        self._append_mcu_log(f"{output}\n[Finished with status: {'OK' if ok else 'FAILED'}]\n")

    def _on_mcu_upload_file(self) -> None:
        """Prompt for a local file and upload it to the device flash."""
        initial_dir = self.config.project_root or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Upload to MCU Flash",
            initial_dir,
            "Python / Assets (*.py *.mpy *.json *.txt *.csv);;All Files (*)",
        )
        if not file_path:
            return
        port = self._selected_mcu_port()
        target_name = Path(file_path).name
        self._append_mcu_log(f"\n[Uploading '{target_name}' to device flash on port '{port}'...]")
        ok, output = self._mcu_controller.upload_file(file_path, remote_path=target_name, port=port)
        if not ok and self._mcu_controller.is_permission_error(output):
            if self._handle_permission_error(port, output):
                ok, output = self._mcu_controller.upload_file(file_path, remote_path=target_name, port=port)
        self._append_mcu_log(f"{output}\n")

    def _on_mcu_upload_and_debug(self) -> None:
        """Upload target file (e.g. main.py), soft reset device, and stream REPL startup logs."""
        initial_dir = self.config.project_root or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Startup File for Upload & Debug",
            initial_dir,
            "Python Files (*.py);;All Files (*)",
        )
        if not file_path:
            return
        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n--- Starting Upload & Debug Session ({Path(file_path).name} on {port}) ---")
        self._mcu_controller.upload_and_debug(
            file_path=file_path,
            remote_path=Path(file_path).name,
            port=port,
            on_output_line=self._append_mcu_log,
            on_finished=lambda code, msg: self._append_mcu_log(f"\n[Upload & Debug Finished: {msg}]\n"),
        )

    def _on_mcu_soft_reset(self) -> None:
        """Send a soft reset to the microcontroller."""
        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n[Sending Soft Reset to port '{port}'...]")
        ok, msg = self._mcu_controller.soft_reset(port=port)
        if not ok and self._mcu_controller.is_permission_error(msg):
            if self._handle_permission_error(port, msg):
                ok, msg = self._mcu_controller.soft_reset(port=port)
        self._append_mcu_log(f"{msg}\n")

    def _on_mcu_stop_repl(self) -> None:
        """Stop active REPL stream."""
        self._mcu_controller.stop_repl()
        self._append_mcu_log("\n[REPL Monitor Stopped]\n")

    def _on_mcu_refresh_files(self) -> None:
        """Scan and populate on-device flash filesystem tree."""
        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n[Scanning device filesystem on {port}...]\n")
        ok, items = self._mcu_controller.list_device_files(remote_dir="/", port=port)
        self.mcu_fs_tree.clear()
        if not ok:
            self._append_mcu_log("[Failed to retrieve device file listing]\n")
            return

        for it in items:
            item_widget = QTreeWidgetItem([
                str(it.get("name", "")),
                f"{it.get('size', 0)} bytes" if not it.get("is_dir") else "<DIR>",
                "Directory" if it.get("is_dir") else "File",
            ])
            item_widget.setData(0, Qt.ItemDataRole.UserRole, it)
            self.mcu_fs_tree.addTopLevelItem(item_widget)
        self._append_mcu_log(f"[Found {len(items)} items on device]\n")

    def _on_mcu_download_file(self) -> None:
        """Download selected remote file to local project workspace."""
        selected = self.mcu_fs_tree.selectedItems()
        if not selected:
            QMessageBox.information(self, "No File Selected", "Please select a file from the device filesystem tree first.")
            return

        data = selected[0].data(0, Qt.ItemDataRole.UserRole) or {}
        remote_name = data.get("name", "")
        if not remote_name or data.get("is_dir"):
            return

        dest_dir = self.config.project_root or "."
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Downloaded File",
            str(Path(dest_dir) / remote_name),
            "All Files (*)",
        )
        if not save_path:
            return

        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n[Downloading {remote_name} to {save_path}...]")
        ok, msg = self._mcu_controller.download_file(remote_name, save_path, port=port)
        self._append_mcu_log(f"[{msg}]\n")

    def _on_mcu_delete_file(self) -> None:
        """Delete selected file from microcontroller flash."""
        selected = self.mcu_fs_tree.selectedItems()
        if not selected:
            return

        data = selected[0].data(0, Qt.ItemDataRole.UserRole) or {}
        remote_name = data.get("name", "")
        if not remote_name:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete '{remote_name}' from the microcontroller?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        port = self._selected_mcu_port()
        self._append_mcu_log(f"\n[Deleting {remote_name} from {port}...]")
        ok, msg = self._mcu_controller.delete_device_file(remote_name, port=port)
        self._append_mcu_log(f"[{msg}]\n")
        self._on_mcu_refresh_files()

