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

"""Code Audit Anti-Pattern configuration and scanner widget."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from PyQt6 import uic
from PyQt6.QtCore import QPoint, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.anti_pattern_controller import AntiPatternController
from app.indexer.index_manager import IndexManager


class PresetDialog(QDialog):
    """Simple dialog to add a new anti-pattern preset."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Anti-Pattern Preset")
        self.setMinimumWidth(400)
        self.name_input = QLineEdit(self)
        self.regex_input = QLineEdit(self)
        self.severity_combo = QComboBox(self)
        self.severity_combo.addItems(["warning", "error", "info"])
        self.desc_input = QLineEdit(self)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Regex Pattern:", self.regex_input)
        form_layout.addRow("Severity:", self.severity_combo)
        form_layout.addRow("Description:", self.desc_input)
        layout.addLayout(form_layout)

        button_layout = QFormLayout()
        self.save_btn = QPushButton("Save", self)
        self.cancel_btn = QPushButton("Cancel", self)
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addRow(self.save_btn, self.cancel_btn)
        layout.addLayout(button_layout)


class AntiPatternView(QWidget):
    """Widget for managing and running regex code anti-pattern audits."""

    def __init__(
        self,
        index_manager: IndexManager,
        open_file_callback: Callable[[Path, int | None], bool] | None = None,
        controller: AntiPatternController | None = None,
    ) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._open_file_callback = open_file_callback
        self._controller = controller or AntiPatternController(index_manager=index_manager)
        self.presets_list: QListWidget
        self.addButton: QPushButton
        self.deleteButton: QPushButton
        self.scope_combo: QComboBox
        self.path_filter: QLineEdit
        self.scan_button: QPushButton
        self.results_table: QTableWidget
        self.preview_pane: QPlainTextEdit

        self.presets: list[dict[str, object]] = []
        self._last_results: list[dict[str, object]] = []

        self._load_ui()
        self._build_ui()
        self.load_presets()

    def _load_ui(self) -> None:
        """Load and bind the anti-pattern browser Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "anti_pattern_view.ui"
        uic.loadUi(ui_path, self)

        presets_list = self.findChild(QListWidget, "presetsList")
        add_button = self.findChild(QPushButton, "addButton")
        delete_button = self.findChild(QPushButton, "deleteButton")
        scope_combo = self.findChild(QComboBox, "scopeCombo")
        path_filter = self.findChild(QLineEdit, "pathFilter")
        scan_button = self.findChild(QPushButton, "scanButton")
        results_table = self.findChild(QTableWidget, "resultsTable")
        preview_pane = self.findChild(QPlainTextEdit, "previewPane")

        if any(
            w is None
            for w in [
                presets_list,
                add_button,
                delete_button,
                scope_combo,
                path_filter,
                scan_button,
                results_table,
                preview_pane,
            ]
        ):
            raise RuntimeError("Anti-pattern browser UI is missing required widgets.")

        self.presets_list = presets_list
        self.addButton = add_button
        self.deleteButton = delete_button
        self.scope_combo = scope_combo
        self.path_filter = path_filter
        self.scan_button = scan_button
        self.results_table = results_table
        self.preview_pane = preview_pane

    def _build_ui(self) -> None:
        self.scope_combo.addItems(["all", "changed"])
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["File", "Line", "Preset Name", "Severity", "Match", "Content"])
        self.results_table.horizontalHeader().setVisible(True)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(False)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview_pane.setReadOnly(True)

        self.scan_button.clicked.connect(self.run_scan)
        self.addButton.clicked.connect(self.add_preset)
        self.deleteButton.clicked.connect(self.delete_preset)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        self.results_table.cellDoubleClicked.connect(self._on_result_double_clicked)
        self.results_table.customContextMenuRequested.connect(self._on_results_context_menu)

    def load_presets(self) -> None:
        """Load presets config from output dir."""
        self.presets = self._controller.load_presets()
        
        self.presets_list.clear()
        for p in self.presets:
            item = QListWidgetItem(f"{p['name']} ({p['severity']})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if p.get("enabled", True) else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.presets_list.addItem(item)

    def save_presets(self) -> None:
        """Save current presets state back to configuration file."""
        updated = []
        for i in range(self.presets_list.count()):
            item = self.presets_list.item(i)
            p = item.data(Qt.ItemDataRole.UserRole)
            p["enabled"] = (item.checkState() == Qt.CheckState.Checked)
            updated.append(p)
        self.presets = updated

        self._controller.save_presets(self.presets)

    def add_preset(self) -> None:
        """Open PresetDialog and add a new anti-pattern preset definition."""
        dlg = PresetDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.name_input.text().strip()
            regex = dlg.regex_input.text().strip()
            severity = dlg.severity_combo.currentText()
            desc = dlg.desc_input.text().strip()

            if not name or not regex:
                QMessageBox.warning(self, "Invalid Inputs", "Name and Regex pattern are required.")
                return

            try:
                re.compile(regex)
            except re.error as exc:
                QMessageBox.warning(self, "Invalid Regex", f"Failed to compile regex: {exc}")
                return

            preset = {
                "name": name,
                "regex": regex,
                "severity": severity,
                "description": desc,
                "enabled": True,
            }
            
            self.save_presets()
            self.presets.append(preset)
            self._controller.save_presets(self.presets)
            
            self.load_presets()

    def delete_preset(self) -> None:
        """Delete currently selected preset item from config."""
        selected = self.presets_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "Selection Required", "Please select a preset to delete.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete preset: {selected[0].text()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.presets_list.takeItem(self.presets_list.row(selected[0]))
            self.save_presets()
            self.load_presets()

    def run_scan(self) -> None:
        """Run regex anti-patterns scan over loaded file_corpus."""
        self.save_presets()
        active_presets = [p for p in self.presets if p.get("enabled", True)]
        if not active_presets:
            QMessageBox.information(self, "No Active Presets", "No active anti-pattern presets configured.")
            return

        scope = self.scope_combo.currentText()
        filter_text = self.path_filter.text().strip().lower()

        try:
            results = self._controller.run_scan(
                presets=active_presets,
                scope=scope,
                filter_text=filter_text,
            )
        except Exception as e:
            QMessageBox.warning(self, "Scan Error", f"Unable to run anti-pattern scan: {e}")
            return

        self._last_results = results
        self.results_table.clearContents()
        self.results_table.setRowCount(len(results))
        for row, item in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(str(item.get("path", ""))))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(item.get("line", ""))))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(item.get("preset_name", ""))))
            
            severity = str(item.get("severity", "")).lower()
            severity_item = QTableWidgetItem(severity)
            if severity == "error":
                severity_item.setBackground(QColor("#fce8e6"))
                severity_item.setForeground(QColor("#a51d24"))
            elif severity == "warning":
                severity_item.setBackground(QColor("#fef7e0"))
                severity_item.setForeground(QColor("#b06000"))
            elif severity == "info":
                severity_item.setBackground(QColor("#e8f0fe"))
                severity_item.setForeground(QColor("#1a73e8"))
            
            self.results_table.setItem(row, 3, severity_item)
            self.results_table.setItem(row, 4, QTableWidgetItem(str(item.get("match", ""))))
            self.results_table.setItem(row, 5, QTableWidgetItem(str(item.get("content", ""))))

        if results:
            self.results_table.selectRow(0)
            self._render_result(results[0])
        else:
            self.preview_pane.setPlainText("No anti-pattern matches found.")

    def _on_result_selected(self) -> None:
        selected = self.results_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if 0 <= row < len(self._last_results):
            self._render_result(self._last_results[row])

    def _on_result_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._last_results):
            self._open_result_file(self._last_results[row])

    def _on_results_context_menu(self, position: QPoint) -> None:
        row = self.results_table.rowAt(position.y())
        has_selection = (0 <= row < len(self._last_results))

        menu = QMenu(self)
        open_action = None
        copy_path_action = None
        copy_ref_action = None

        if has_selection:
            self.results_table.selectRow(row)
            result = self._last_results[row]
            path_text = str(result.get("path", "")).strip()

            open_action = menu.addAction("Open File")
            copy_path_action = menu.addAction("Copy Path")
            copy_ref_action = menu.addAction("Copy Reference Location")
            menu.addSeparator()

        export_csv_action = menu.addAction("Export All Results to CSV...")
        export_csv_action.setEnabled(len(self._last_results) > 0)

        selected = menu.exec(self.results_table.viewport().mapToGlobal(position))
        if not selected:
            return

        if selected == open_action and has_selection:
            self._open_result_file(result)
        elif selected == copy_path_action and has_selection:
            folder_path = self._controller.containing_folder_path(path_text)
            if folder_path:
                QApplication.clipboard().setText(folder_path)
        elif selected == copy_ref_action and has_selection:
            line_str = str(result.get("line", ""))
            QApplication.clipboard().setText(self._controller.reference_location(path_text=path_text, line_text=line_str))
        elif selected == export_csv_action:
            self.export_results_to_csv()

    def export_results_to_csv(self) -> None:
        """Prompt user for a file location and export all scan results to CSV."""
        from PyQt6.QtWidgets import QFileDialog

        if not self._last_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results to CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        try:
            self._controller.export_results_to_csv(self._last_results, file_path)
            QMessageBox.information(self, "Export Successful", f"Successfully exported {len(self._last_results)} results to:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Failed to export results: {exc}")

    def _open_result_file(self, item: dict[str, object]) -> None:
        path_text = str(item.get("path", "")).strip()
        if not path_text:
            return
        candidate = self._controller.resolve_result_path(path_text)
        if candidate is None:
            return
        if candidate.exists():
            line = item.get("line")
            line_number = int(line) if line is not None and str(line).isdigit() else None
            if self._open_file_callback is not None:
                handled = self._open_file_callback(candidate, line_number)
                if handled:
                    return

            if self._controller.open_external_editor(path_text, line_number):
                return

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))

    def _render_result(self, item: dict[str, object]) -> None:
        path = str(item.get("path", ""))
        line = item.get("line")
        line_number = int(line) if str(line).isdigit() else None

        rendered = [
            f"Rule: {item.get('preset_name')}",
            f"Severity: {item.get('severity')}",
            f"Description: {item.get('description')}",
            f"File: {path}",
            f"Line: {line_number}",
            f"Match Text: {item.get('match')}",
            "",
        ]
        context_text = self._controller.line_context(
            path=path,
            line_number=line_number,
            fallback_content=f"Content: {item.get('content')}",
            context=4,
        )
        rendered.append(context_text)
            
        self.preview_pane.setPlainText("\n".join(rendered))
