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

"""Search browser widget for query input and result browsing."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import QPoint, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHeaderView,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.indexer.index_manager import IndexManager
from app.search.search_engine import search_snapshot


class SearchBrowser(QWidget):
    """Widget providing near-instant search over in-memory index state."""

    def __init__(self, index_manager: IndexManager) -> None:
        super().__init__()
        self.index_manager = index_manager
        self.query_input: QLineEdit
        self.scope_combo: QComboBox
        self.changed_only: QCheckBox
        self.search_button: QPushButton
        self.results_table: QTableWidget
        self.preview_pane: QPlainTextEdit
        self._last_results: list[dict[str, object]] = []
        self._load_ui()
        self._build_ui()

    def _load_ui(self) -> None:
        """Load and bind the search browser Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "search_browser.ui"
        uic.loadUi(ui_path, self)

        query_input = self.findChild(QLineEdit, "queryInput")
        scope_combo = self.findChild(QComboBox, "scopeCombo")
        changed_only = self.findChild(QCheckBox, "changedOnly")
        search_button = self.findChild(QPushButton, "searchButton")
        results_table = self.findChild(QTableWidget, "resultsTable")
        preview_pane = self.findChild(QPlainTextEdit, "previewPane")
        if any(widget is None for widget in [query_input, scope_combo, changed_only, search_button, results_table, preview_pane]):
            raise RuntimeError("Search browser UI is missing required widgets.")

        self.query_input = query_input
        self.scope_combo = scope_combo
        self.changed_only = changed_only
        self.search_button = search_button
        self.results_table = results_table
        self.preview_pane = preview_pane

    def _build_ui(self) -> None:
        self.scope_combo.addItems(["all", "files", "symbols", "excel"])
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["Type", "File Type", "Path", "Line", "Title", "Preview"])
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

        self.search_button.clicked.connect(self.run_search)
        self.query_input.returnPressed.connect(self.run_search)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        self.results_table.cellDoubleClicked.connect(self._on_result_double_clicked)
        self.results_table.customContextMenuRequested.connect(self._on_results_context_menu)

    def run_search(self) -> None:
        """Execute a search over in-memory indexes and populate the table."""
        query = self.query_input.text().strip()
        results = search_snapshot(
            file_corpus=self.index_manager.state.file_corpus,
            symbols=self.index_manager.state.symbols,
            excel_rows=self.index_manager.state.excel_rows,
            query=query,
            scope=self.scope_combo.currentText(),
            limit=100,
        )
        self._last_results = results

        self.results_table.clearContents()
        self.results_table.setRowCount(len(results))
        for row, item in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(str(item.get("type", ""))))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(item.get("file_type", ""))))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(item.get("path", ""))))
            self.results_table.setItem(row, 3, QTableWidgetItem(str(item.get("line", ""))))
            self.results_table.setItem(row, 4, QTableWidgetItem(str(item.get("title", ""))))
            self.results_table.setItem(row, 5, QTableWidgetItem(str(item.get("preview", ""))))

        if results:
            self.results_table.selectRow(0)
            self._render_result(results[0])
        else:
            self.preview_pane.setPlainText("No results.")

    def set_query(self, query: str, scope: str | None = None, execute: bool = True) -> None:
        """Set query/scope from external navigation controls and optionally run."""
        self.query_input.setText(query)
        if scope is not None:
            scope_index = self.scope_combo.findText(scope)
            if scope_index >= 0:
                self.scope_combo.setCurrentIndex(scope_index)
        if execute:
            self.run_search()

    def _on_result_selected(self) -> None:
        """Render rich preview details for the currently selected result row."""
        selected = self.results_table.selectionModel().selectedRows()
        if not selected:
            return

        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(self._last_results):
            return

        item = self._last_results[row_index]
        self._render_result(item)

    def _on_result_double_clicked(self, row: int, _column: int) -> None:
        """Open selected result file on double click."""
        if row < 0 or row >= len(self._last_results):
            return
        self._open_result_file(self._last_results[row])

    def _on_results_context_menu(self, position: QPoint) -> None:
        """Show result context menu with open/copy actions."""
        row = self.results_table.rowAt(position.y())
        if row < 0 or row >= len(self._last_results):
            return

        self.results_table.selectRow(row)
        result = self._last_results[row]
        path_text = str(result.get("path", "")).strip()
        reference = self._reference_location(result)

        menu = QMenu(self)
        open_action = menu.addAction("Open File")
        menu.addSeparator()
        copy_path_action = menu.addAction("Copy Path")
        copy_reference_action = menu.addAction("Copy Reference Location")
        menu.setDefaultAction(copy_path_action)

        if not path_text:
            open_action.setEnabled(False)
            copy_path_action.setEnabled(False)
            copy_reference_action.setEnabled(False)

        selected = menu.exec(self.results_table.viewport().mapToGlobal(position))
        if selected is None:
            return
        if selected == open_action:
            self._open_result_file(result)
            return
        if selected == copy_path_action and path_text:
            QApplication.clipboard().setText(path_text)
            return
        if selected == copy_reference_action and reference:
            QApplication.clipboard().setText(reference)

    def _resolve_path(self, path_text: str) -> Path | None:
        """Resolve index path to local filesystem path."""
        if not path_text:
            return None
        candidate = Path(path_text)
        if candidate.is_absolute():
            return candidate
        repo_root = Path(self.index_manager.config.project_root or Path.cwd())
        return (repo_root / candidate).resolve()

    def _open_result_file(self, item: dict[str, object]) -> None:
        """Open file path from a result row in the desktop shell."""
        path_text = str(item.get("path", "")).strip()
        resolved = self._resolve_path(path_text)
        if resolved is None or not resolved.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))

    def _reference_location(self, item: dict[str, object]) -> str:
        """Build path:line reference text for clipboard actions."""
        path_text = str(item.get("path", "")).strip()
        line = item.get("line")
        line_text = str(line).strip() if line is not None else ""
        if path_text and line_text and line_text != "None":
            return f"{path_text}:{line_text}"
        return path_text

    def _render_result(self, item: dict[str, object]) -> None:
        """Render one result into the preview pane."""
        item_type = str(item.get("type", ""))
        path = str(item.get("path", ""))
        line = item.get("line")
        title = str(item.get("title", ""))
        preview = str(item.get("preview", ""))

        if item_type in {"file", "symbol"} and path:
            line_number = int(line) if str(line).isdigit() else None
            self.preview_pane.setPlainText(self._line_context(path=path, line_number=line_number, fallback=preview, title=title))
            return

        if item_type == "excel":
            self.preview_pane.setPlainText(
                "\n".join(
                    [
                        "Type: excel",
                        f"File: {path}",
                        f"Row: {line}",
                        f"Field: {title}",
                        f"Value: {preview}",
                    ]
                )
            )
            return

        self.preview_pane.setPlainText(preview)

    def _line_context(self, path: str, line_number: int | None, fallback: str, title: str, context: int = 3) -> str:
        """Build a multi-line context preview from in-memory file corpus."""
        source = self.index_manager.state.file_corpus.get(path, "")
        lines = source.splitlines()
        if not lines:
            return "\n".join([f"Path: {path}", f"Title: {title}", f"Preview: {fallback}"])

        resolved_line = max(1, line_number or 1)
        start = max(1, resolved_line - context)
        end = min(len(lines), resolved_line + context)

        rendered = [f"Path: {path}", f"Line: {resolved_line}", ""]
        for ln in range(start, end + 1):
            marker = ">" if ln == resolved_line else " "
            rendered.append(f"{marker} {ln:4d} | {lines[ln - 1]}")
        return "\n".join(rendered)
