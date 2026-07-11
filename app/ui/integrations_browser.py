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
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.controllers.integrations_controller import IntegrationsController
from app.services.mcp_server_manager import MCPServerManager


class IntegrationsBrowser(QWidget):
    """Manage MCP server settings and control."""

    def __init__(
        self,
        config: AppConfig,
        mcp_manager: MCPServerManager,
        on_project_root_changed: Callable[[str], None] | None = None,
        controller: IntegrationsController | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.mcp_manager = mcp_manager
        self._on_project_root_changed = on_project_root_changed
        self._controller = controller or IntegrationsController(
            config=config,
            mcp_manager=mcp_manager,
            on_project_root_changed=on_project_root_changed,
        )
        self._build_ui()
        self.sync_from_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        mcp_group = QGroupBox("MCP Server Settings & Control", self)
        mcp_layout = QVBoxLayout(mcp_group)
        mcp_form = QFormLayout()
        self.mcp_transport_combo = QComboBox(mcp_group)
        self.mcp_transport_combo.setObjectName("mcpTransportCombo")
        self.mcp_transport_combo.addItems(["SSE", "stdio"])
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
        mcp_form.addRow("Transport:", self.mcp_transport_combo)
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

        root.addWidget(mcp_group)

        # MCP Server API Explorer Group
        explorer_group = QGroupBox("MCP Server API Explorer", self)
        explorer_layout = QVBoxLayout(explorer_group)

        search_layout = QHBoxLayout()
        self.mcp_search_input = QLineEdit(explorer_group)
        self.mcp_search_input.setObjectName("mcpSearchInput")
        self.mcp_search_input.setPlaceholderText("Enter query to search indexed codebase...")
        self.mcp_search_button = QPushButton("Search via MCP", explorer_group)
        self.mcp_search_button.setObjectName("mcpSearchButton")
        self.mcp_load_ast_button = QPushButton("Load AST / CST", explorer_group)
        self.mcp_load_ast_button.setObjectName("mcpLoadAstButton")
        search_layout.addWidget(self.mcp_search_input)
        search_layout.addWidget(self.mcp_search_button)
        search_layout.addWidget(self.mcp_load_ast_button)
        explorer_layout.addLayout(search_layout)

        self.mcp_explorer_tree = QTreeWidget(explorer_group)
        self.mcp_explorer_tree.setObjectName("mcpExplorerTree")
        self.mcp_explorer_tree.setHeaderLabels(["File / AST Node", "Type", "Details / Preview"])
        self.mcp_explorer_tree.setColumnCount(3)
        explorer_layout.addWidget(self.mcp_explorer_tree)

        root.addWidget(explorer_group)
        root.addStretch(1)

        self.mcp_save_button.clicked.connect(self.save_settings)
        self.mcp_start_button.clicked.connect(self.start_mcp_server)
        self.mcp_stop_button.clicked.connect(self.stop_mcp_server)
        self.mcp_probe_button.clicked.connect(self.probe_mcp_server)
        self.mcp_search_button.clicked.connect(self.search_via_mcp)
        self.mcp_load_ast_button.clicked.connect(self.load_selected_ast)
        self.mcp_explorer_tree.itemDoubleClicked.connect(self.handle_item_double_clicked)
        self.mcp_transport_combo.currentTextChanged.connect(self.handle_transport_changed)

    def handle_transport_changed(self, text: str) -> None:
        """Enable or disable network controls depending on transport mode."""
        is_sse = (text == "SSE")
        self.mcp_host_edit.setEnabled(is_sse)
        self.mcp_port_spin.setEnabled(is_sse)
        self.mcp_start_button.setEnabled(is_sse)
        self.mcp_stop_button.setEnabled(is_sse)
        self.mcp_probe_button.setEnabled(is_sse)
        self.mcp_search_button.setEnabled(is_sse)
        self.mcp_load_ast_button.setEnabled(is_sse)
        self.refresh_status()

    def sync_from_config(self) -> None:
        """Refresh UI controls from current app config."""
        self.mcp_host_edit.setText((self.config.mcp_host or "127.0.0.1").strip() or "127.0.0.1")
        self.mcp_port_spin.setValue(int(self.config.mcp_port or 8765))
        self.mcp_token_edit.setText(self.config.mcp_auth_token or "")
        self.mcp_autostart_check.setChecked(bool(self.config.mcp_autostart))
        
        transport = (self.config.mcp_transport or "streamable-http").strip().lower()
        if transport in ("stdio", "standard-io"):
            self.mcp_transport_combo.setCurrentText("stdio")
        else:
            self.mcp_transport_combo.setCurrentText("SSE")
        self.refresh_status()

    def save_settings(self) -> None:
        """Persist integration settings to config file."""
        transport_text = self.mcp_transport_combo.currentText().strip()
        transport = "stdio" if transport_text == "stdio" else "streamable-http"
        self._controller.save_settings(
            host=self.mcp_host_edit.text().strip(),
            port=self.mcp_port_spin.value(),
            token=self.mcp_token_edit.text().strip(),
            transport=transport,
            autostart=self.mcp_autostart_check.isChecked(),
        )
        self.refresh_status("Integration settings saved.")

    def refresh_status(self, message: str | None = None) -> None:
        """Refresh MCP status label."""
        transport_text = self.mcp_transport_combo.currentText().strip()
        suffix = f" | {message}" if message else ""
        if transport_text == "stdio":
            self.mcp_status_label.setText(f"MCP Status: stdio active. Run via CLI/client.{suffix}")
        else:
            running = self.mcp_manager.is_running()
            endpoint = self.mcp_manager.endpoint()
            self.mcp_status_label.setText(f"MCP Status: {'running' if running else 'stopped'} @ {endpoint}{suffix}")

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
        ok, message = self._controller.probe_mcp_server(token)
        if ok:
            QMessageBox.information(self, "Probe Success", f"MCP probe status: {message}")
            self.refresh_status(f"Probe OK ({message})")
        else:
            QMessageBox.warning(self, "Probe Failed", message)
            self.refresh_status("Probe failed")

    def search_via_mcp(self) -> None:
        """Execute a search against the MCP server and list files in the tree."""
        query = self.mcp_search_input.text().strip()
        if not query:
            return
        
        token = self.mcp_token_edit.text().strip()
        self.mcp_explorer_tree.clear()
        
        ok, response = self._controller.search_via_mcp(query, token)
        if not ok:
            QMessageBox.warning(self, "MCP Search Failed", str(response))
            return
            
        results = response.get("results", []) if isinstance(response, dict) else []
        if not results:
            QTreeWidgetItem(self.mcp_explorer_tree, ["No results found.", "", ""])
            return
            
        seen_files = set()
        for res in results:
            path = res.get("path")
            if not path or path in seen_files:
                continue
            seen_files.add(path)
            
            file_type = res.get("file_type", "")
            preview = res.get("preview", "")
            item = QTreeWidgetItem(self.mcp_explorer_tree, [path, f"file ({file_type})", preview])
            item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "file", "path": path})

    def load_selected_ast(self) -> None:
        """Fetch AST for the selected file from the MCP server and populate child items."""
        selected = self.mcp_explorer_tree.selectedItems()
        if not selected:
            QMessageBox.information(self, "MCP Explorer", "Please select a file from the list first.")
            return
        
        item = selected[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict) or data.get("kind") != "file":
            QMessageBox.information(self, "MCP Explorer", "Please select a file item (not an AST node).")
            return
            
        path = data.get("path")
        token = self.mcp_token_edit.text().strip()
        
        ok, ast_data = self._controller.get_ast_via_mcp(path, token)
        if not ok:
            QMessageBox.warning(self, "MCP AST Load Failed", str(ast_data))
            return
            
        self._populate_ast(item, ast_data)
        self.mcp_explorer_tree.expandItem(item)

    def handle_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Double click a file to trigger load_selected_ast."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and isinstance(data, dict) and data.get("kind") == "file":
            self.load_selected_ast()

    def _populate_ast(self, parent_item: QTreeWidgetItem, data: dict[str, Any]) -> None:
        parent_item.takeChildren()  # Clear existing children first
        
        if not isinstance(data, dict):
            return
            
        language = data.get("language", "python")
        if language == "python":
            # Add classes
            classes = data.get("classes", [])
            if classes:
                classes_root = QTreeWidgetItem(["Classes", "", ""])
                parent_item.addChild(classes_root)
                for cls in classes:
                    cls_name = cls.get("name", "<class>")
                    cls_doc = cls.get("docstring", "").strip()
                    cls_item = QTreeWidgetItem([cls_name, "class", cls_doc[:80] if cls_doc else ""])
                    classes_root.addChild(cls_item)
                    for method in cls.get("methods", []):
                        m_sig = method.get("signature", "")
                        m_doc = method.get("docstring", "").strip()
                        m_item = QTreeWidgetItem([m_sig, "method", m_doc[:80] if m_doc else ""])
                        cls_item.addChild(m_item)
            
            # Add functions
            funcs = data.get("functions", [])
            if funcs:
                funcs_root = QTreeWidgetItem(["Functions", "", ""])
                parent_item.addChild(funcs_root)
                for func in funcs:
                    f_sig = func.get("signature", "")
                    f_doc = func.get("docstring", "").strip()
                    f_item = QTreeWidgetItem([f_sig, "function", f_doc[:80] if f_doc else ""])
                    funcs_root.addChild(f_item)
            
            # Add variables
            vars_ = data.get("variables", [])
            if vars_:
                vars_root = QTreeWidgetItem(["Variables", "", ""])
                parent_item.addChild(vars_root)
                for var in vars_:
                    v_name = var.get("name", "")
                    v_line = str(var.get("line", ""))
                    v_item = QTreeWidgetItem([v_name, "variable", f"Defined on line {v_line}"])
                    vars_root.addChild(v_item)
            
            # Add imports
            imports = data.get("imports", [])
            if imports:
                imports_root = QTreeWidgetItem(["Imports", "", ""])
                parent_item.addChild(imports_root)
                for imp in imports:
                    i_name = imp.get("name", "")
                    i_as = imp.get("asname", "")
                    i_line = str(imp.get("line", ""))
                    as_suffix = f" as {i_as}" if i_as else ""
                    i_item = QTreeWidgetItem([f"{i_name}{as_suffix}", "import", f"Line {i_line}"])
                    imports_root.addChild(i_item)

        elif language == "c":
            # Add structs
            structs = data.get("classes", [])
            if structs:
                structs_root = QTreeWidgetItem(["Structs", "", ""])
                parent_item.addChild(structs_root)
                for struct in structs:
                    s_name = struct.get("name", "")
                    s_line = str(struct.get("start_line", ""))
                    s_item = QTreeWidgetItem([s_name, "struct", f"Line {s_line}"])
                    structs_root.addChild(s_item)

            # Add functions
            funcs = data.get("functions", [])
            if funcs:
                funcs_root = QTreeWidgetItem(["Functions", "", ""])
                parent_item.addChild(funcs_root)
                for func in funcs:
                    f_name = func.get("name", "")
                    f_line = str(func.get("start_line", ""))
                    f_item = QTreeWidgetItem([f_name, "function", f"Line {f_line}"])
                    funcs_root.addChild(f_item)

            # Add enums
            enums = data.get("enums", [])
            if enums:
                enums_root = QTreeWidgetItem(["Enums", "", ""])
                parent_item.addChild(enums_root)
                for enum in enums:
                    e_name = enum.get("name", "")
                    e_line = str(enum.get("start_line", ""))
                    e_item = QTreeWidgetItem([e_name, "enum", f"Line {e_line}"])
                    enums_root.addChild(e_item)

