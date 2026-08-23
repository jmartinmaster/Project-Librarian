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
"""Settings dialog for project paths, indexing, and Excel options."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.controllers.settings_controller import SettingsController
from app.config import AppConfig


class SettingsView(QDialog):
    """Dialog for modifying persistent application configuration."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._controller = SettingsController()

        self.project_root_edit: QLineEdit
        self.output_dir_edit: QLineEdit
        self.refresh_spin: QSpinBox
        self.index_python_check: QCheckBox
        self.use_cst_check: QCheckBox
        self.index_c_check: QCheckBox
        self.extensions_list: QListWidget
        self.extension_input: QLineEdit
        self.excluded_list: QListWidget
        self.excluded_input: QLineEdit
        self.excel_folder_edit: QLineEdit
        self.excel_columns_list: QListWidget
        self.external_editor_edit: QLineEdit
        self._button_box: QDialogButtonBox
        self._project_root_browse_button: QPushButton
        self._output_dir_browse_button: QPushButton
        self._excel_folder_browse_button: QPushButton
        self._load_headers_button: QPushButton
        self._extension_add_button: QPushButton
        self._extension_remove_button: QPushButton
        self._excluded_add_button: QPushButton
        self._excluded_remove_button: QPushButton

        self._load_ui()

        self.refresh_spin.setRange(0, 3600)
        self.refresh_spin.setValue(config.refresh_interval_seconds)
        self.index_python_check.setChecked(config.index_python)
        self.use_cst_check.setChecked(config.use_cst)
        self.index_c_check.setChecked(config.index_c)
        self.thread_count_spin.setValue(config.indexing_thread_count)

        self.project_root_edit.setText(config.project_root)
        self.output_dir_edit.setText(config.output_dir)
        self.micropython_mode_check.setChecked(bool(getattr(config, "micropython_mode", False)))
        self.micropython_live_code_check.setChecked(bool(getattr(config, "micropython_live_code", False)))
        self.micropython_port_edit.setText(getattr(config, "micropython_port", "auto") or "auto")
        self.micropython_runner_edit.setText(getattr(config, "micropython_runner_cmd", "mpremote") or "mpremote")
        for ext in config.file_extensions:
            self.extensions_list.addItem(QListWidgetItem(ext))

        for item in config.excluded_dirs:
            self.excluded_list.addItem(QListWidgetItem(item))
        self.excel_folder_edit.setText(config.excel_folder)
        self.external_editor_edit.setText(config.external_editor_cmd)
        self._wire_signals()
        self._load_excel_columns_from_config()

    def _load_ui(self) -> None:
        """Load and bind the settings dialog Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "settings_view.ui"
        uic.loadUi(ui_path, self)

        self.project_root_edit = self._require_widget(QLineEdit, "projectRootEdit")
        self.output_dir_edit = self._require_widget(QLineEdit, "outputDirEdit")
        self.refresh_spin = self._require_widget(QSpinBox, "refreshSpin")
        self.index_python_check = self._require_widget(QCheckBox, "indexPythonCheck")

        from PyQt6.QtWidgets import QVBoxLayout
        indexing_layout = self.findChild(QVBoxLayout, "indexingLayout")
        self.use_cst_check = QCheckBox("Use CST (Concrete Syntax Tree) via libcst")
        self.use_cst_check.setObjectName("useCstCheck")
        if indexing_layout is not None:
            indexing_layout.insertWidget(1, self.use_cst_check)

        self.index_c_check = self._require_widget(QCheckBox, "indexCCheck")
        self.extensions_list = self._require_widget(QListWidget, "extensionsList")
        self.extension_input = self._require_widget(QLineEdit, "extensionInput")
        self.excluded_list = self._require_widget(QListWidget, "excludedList")
        self.excluded_input = self._require_widget(QLineEdit, "excludedInput")
        self.excel_folder_edit = self._require_widget(QLineEdit, "excelFolderEdit")
        self.excel_columns_list = self._require_widget(QListWidget, "excelColumnsList")

        self.generalForm = self.findChild(QFormLayout, "generalForm")
        if self.generalForm is None:
            raise RuntimeError("Settings dialog UI is missing required layout: generalForm")
        
        self.external_editor_edit = QLineEdit(self)
        self.external_editor_edit.setObjectName("externalEditorEdit")
        self.external_editor_edit.setPlaceholderText('e.g., code -g "{file}:{line}"')
        self.generalForm.addRow("External Editor Command:", self.external_editor_edit)

        # Thread count setup
        self.thread_count_spin = QSpinBox(self)
        self.thread_count_spin.setObjectName("threadCountSpin")
        self.thread_count_spin.setRange(1, 24)
        import os
        cores = os.cpu_count() or 4
        self.thread_count_spin.setToolTip(f"Set indexing thread count. Recommended: do not exceed system cores ({cores}).")
        self.generalForm.addRow(f"Indexing Thread Count (System Cores: {cores}):", self.thread_count_spin)

        # MicroPython settings
        self.micropython_mode_check = QCheckBox("Enable MicroPython Workspace Mode", self)
        self.micropython_mode_check.setObjectName("micropythonModeCheck")
        self.micropython_mode_check.setToolTip("Optimizes indexing for MicroPython codebases and enables hardware tools.")
        self.generalForm.addRow("MicroPython Mode:", self.micropython_mode_check)

        self.micropython_live_code_check = QCheckBox("Enable Live Code Execution (Safety Guard)", self)
        self.micropython_live_code_check.setObjectName("micropythonLiveCodeCheck")
        self.micropython_live_code_check.setToolTip("When checked, permits uploading and executing code on connected microcontrollers.")
        self.generalForm.addRow("Live Code Guard:", self.micropython_live_code_check)

        self.micropython_port_edit = QLineEdit(self)
        self.micropython_port_edit.setObjectName("micropythonPortEdit")
        self.micropython_port_edit.setPlaceholderText("auto or /dev/ttyACM0 or COM3")
        self.generalForm.addRow("MCU Device Port:", self.micropython_port_edit)

        self.micropython_runner_edit = QLineEdit(self)
        self.micropython_runner_edit.setObjectName("micropythonRunnerEdit")
        self.micropython_runner_edit.setPlaceholderText("mpremote")
        self.generalForm.addRow("MCU Runner Command:", self.micropython_runner_edit)

        self._button_box = self._require_widget(QDialogButtonBox, "buttonBox")
        self._project_root_browse_button = self._require_widget(QPushButton, "projectRootBrowseButton")
        self._output_dir_browse_button = self._require_widget(QPushButton, "outputDirBrowseButton")
        self._excel_folder_browse_button = self._require_widget(QPushButton, "excelFolderBrowseButton")
        self._load_headers_button = self._require_widget(QPushButton, "loadHeadersButton")
        self._extension_add_button = self._require_widget(QPushButton, "extensionAddButton")
        self._extension_remove_button = self._require_widget(QPushButton, "extensionRemoveButton")
        self._excluded_add_button = self._require_widget(QPushButton, "excludedAddButton")
        self._excluded_remove_button = self._require_widget(QPushButton, "excludedRemoveButton")

    def _wire_signals(self) -> None:
        """Connect UI signals to dialog behavior."""
        self._button_box.accepted.connect(self._save_and_accept)
        self._button_box.rejected.connect(self.reject)

        self._project_root_browse_button.clicked.connect(self._pick_project_root)
        self._output_dir_browse_button.clicked.connect(self._pick_output_dir)
        self._excel_folder_browse_button.clicked.connect(self._pick_excel_folder)
        self._load_headers_button.clicked.connect(self._load_excel_columns_from_disk)

        self._extension_add_button.clicked.connect(self._add_extension)
        self._extension_remove_button.clicked.connect(self._remove_extension)
        self._excluded_add_button.clicked.connect(self._add_excluded_dir)
        self._excluded_remove_button.clicked.connect(self._remove_excluded_dir)

    def _require_widget(self, widget_type: type, object_name: str):
        widget = self.findChild(widget_type, object_name)
        if widget is None:
            raise RuntimeError(f"Settings dialog UI is missing widget: {object_name}")
        return widget

    def _pick_project_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Project Root", self.project_root_edit.text(), options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self.project_root_edit.setText(path)

    def _pick_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_dir_edit.text(), options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self.output_dir_edit.setText(path)

    def _pick_excel_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Excel Folder", self.excel_folder_edit.text(), options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self.excel_folder_edit.setText(path)

    def _load_excel_columns_from_config(self) -> None:
        self.excel_columns_list.clear()
        for column in self.config.excel_keyword_columns:
            item = QListWidgetItem(column)
            item.setCheckState(Qt.CheckState.Checked)
            self.excel_columns_list.addItem(item)

    def _load_excel_columns_from_disk(self) -> None:
        self.excel_columns_list.clear()
        headers = self._controller.discover_excel_columns(self.excel_folder_edit.text())
        for header in headers:
            item = QListWidgetItem(header)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.excel_columns_list.addItem(item)

    def _save_and_accept(self) -> None:
        self.config.project_root = self.project_root_edit.text().strip()
        self.config.mvc_editor_root = self.config.project_root
        self.config.output_dir = self.output_dir_edit.text().strip() or "build"
        self.config.refresh_interval_seconds = int(self.refresh_spin.value())
        self.config.index_python = self.index_python_check.isChecked()
        self.config.use_cst = self.use_cst_check.isChecked()
        self.config.index_c = self.index_c_check.isChecked()
        self.config.file_extensions = [self.extensions_list.item(i).text() for i in range(self.extensions_list.count())]
        self.config.excluded_dirs = [self.excluded_list.item(i).text() for i in range(self.excluded_list.count())]
        self.config.excel_folder = self.excel_folder_edit.text().strip()
        self.config.excel_keyword_columns = [
            self.excel_columns_list.item(i).text()
            for i in range(self.excel_columns_list.count())
            if self.excel_columns_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        self.config.external_editor_cmd = self.external_editor_edit.text().strip()
        self.config.indexing_thread_count = int(self.thread_count_spin.value())
        self.config.micropython_mode = self.micropython_mode_check.isChecked()
        self.config.micropython_live_code = self.micropython_live_code_check.isChecked()
        self.config.micropython_port = self.micropython_port_edit.text().strip() or "auto"
        self.config.micropython_runner_cmd = self.micropython_runner_edit.text().strip() or "mpremote"

        self._controller.persist_config(self.config)
        self.accept()

    def _add_extension(self) -> None:
        """Add a normalized file extension entry to the list."""
        raw = self.extension_input.text().strip()
        if not raw:
            return
        value = raw if raw.startswith(".") else f".{raw}"
        existing = {self.extensions_list.item(i).text().lower() for i in range(self.extensions_list.count())}
        if value.lower() in existing:
            QMessageBox.information(self, "Duplicate Extension", f"{value} is already in the list.")
            return
        self.extensions_list.addItem(QListWidgetItem(value))
        self.extension_input.clear()

    def _remove_extension(self) -> None:
        """Remove selected extension entries from the list."""
        for item in self.extensions_list.selectedItems():
            self.extensions_list.takeItem(self.extensions_list.row(item))

    def _add_excluded_dir(self) -> None:
        """Add an excluded directory name to the list."""
        value = self.excluded_input.text().strip().strip("/")
        if not value:
            return
        existing = {self.excluded_list.item(i).text().lower() for i in range(self.excluded_list.count())}
        if value.lower() in existing:
            QMessageBox.information(self, "Duplicate Directory", f"{value} is already in the list.")
            return
        self.excluded_list.addItem(QListWidgetItem(value))
        self.excluded_input.clear()

    def _remove_excluded_dir(self) -> None:
        """Remove selected excluded directory entries from the list."""
        for item in self.excluded_list.selectedItems():
            self.excluded_list.takeItem(self.excluded_list.row(item))
