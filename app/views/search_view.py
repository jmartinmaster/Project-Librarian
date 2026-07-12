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
from typing import Callable

from PyQt6 import uic
from PyQt6.QtCore import QPoint, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.controllers.path_controller import PathController
from app.controllers.search_controller import SearchController
from app.indexer.index_manager import IndexManager


class SearchView(QWidget):
    """Widget providing near-instant search over in-memory index state."""

    def __init__(
        self,
        index_manager: IndexManager,
        open_file_callback: Callable[[Path, int | None], bool] | None = None,
        controller: SearchController | None = None,
        path_controller: PathController | None = None,
    ) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._open_file_callback = open_file_callback
        self._controller = controller or SearchController(index_manager=index_manager)
        self._path_controller = path_controller or PathController(index_manager=index_manager)
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
        ui_path = Path(__file__).resolve().parent / "forms" / "search_view.ui"
        uic.loadUi(ui_path, self)

        query_input = self.findChild(QLineEdit, "queryInput")
        scope_combo = self.findChild(QComboBox, "scopeCombo")
        changed_only = self.findChild(QCheckBox, "changedOnly")
        search_button = self.findChild(QPushButton, "searchButton")
        results_table = self.findChild(QTableWidget, "resultsTable")
        preview_pane = self.findChild(QPlainTextEdit, "previewPane")
        controls_layout = self.findChild(QHBoxLayout, "controlsLayout")
        if any(widget is None for widget in [query_input, scope_combo, changed_only, search_button, results_table, preview_pane, controls_layout]):
            raise RuntimeError("Search browser UI is missing required widgets.")

        self.query_input = query_input
        self.scope_combo = scope_combo
        self.changed_only = changed_only
        self.search_button = search_button
        self.results_table = results_table
        self.preview_pane = preview_pane
        self.controls_layout = controls_layout

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

        self.match_case = QCheckBox("Match Case", self)
        self.match_case.setObjectName("matchCase")
        self.use_regex = QCheckBox("Use Regex", self)
        self.use_regex.setObjectName("useRegex")
        self.match_case.stateChanged.connect(self.run_search)
        self.use_regex.stateChanged.connect(self.run_search)
        self.controls_layout.addWidget(self.match_case)
        self.controls_layout.addWidget(self.use_regex)

    def run_search(self) -> None:
        """Execute a search over in-memory indexes and populate the table."""
        query = self.query_input.text().strip()
        match_case = self.match_case.isChecked() if hasattr(self, "match_case") else False
        use_regex = self.use_regex.isChecked() if hasattr(self, "use_regex") else False

        results = self._controller.run_search(
            query=query,
            scope=self.scope_combo.currentText(),
            limit=100,
            match_case=match_case,
            use_regex=use_regex,
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
        """Show result context menu with open/copy/export actions."""
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
            reference = self._reference_location(result)

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
            folder_path = self._path_controller.containing_folder_path(path_text)
            if folder_path:
                QApplication.clipboard().setText(folder_path)
        elif selected == copy_ref_action and has_selection:
            QApplication.clipboard().setText(reference)
        elif selected == export_csv_action:
            self.export_results_to_csv()

    def export_results_to_csv(self) -> None:
        """Prompt user for a file location and export all search results to CSV."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        if not self._last_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Search Results to CSV",
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

    def _resolve_path(self, path_text: str) -> Path | None:
        """Resolve index path to local filesystem path."""
        return self._path_controller.resolve_path(path_text)

    def _open_result_file(self, item: dict[str, object]) -> None:
        """Open file path from a result row in the desktop shell."""
        path_text = str(item.get("path", "")).strip()
        resolved = self._resolve_path(path_text)
        if resolved is None or not resolved.exists():
            # If the path doesn't exist, log a message to status bar or print it
            print(f"[SearchBrowser] Warning: Could not resolve path to open: {path_text}")
            return
        
        line = item.get("line")
        line_number = int(line) if line is not None and str(line).isdigit() else None
        
        # 1. Attempt to open in embedded MVC editor tab via callback
        if self._open_file_callback is not None:
            handled = self._open_file_callback(resolved, line_number)
            if handled:
                return

        # 2. Fallback to configured external editor (e.g. VS Code, Sublime)
        if self._controller.open_external_editor(path_text, line_number):
            return

        # 3. Final fallback: open with system default handler
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))

    def _reference_location(self, item: dict[str, object]) -> str:
        """Build path:line reference text for clipboard actions."""
        path_text = str(item.get("path", "")).strip()
        line = item.get("line")
        line_text = str(line).strip() if line is not None else ""
        if line_text == "None":
            line_text = ""
        return self._path_controller.reference_location(path_text=path_text, line_text=line_text)

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
        return self._controller.line_context(
            path=path,
            line_number=line_number,
            fallback=fallback,
            title=title,
            context=context,
        )
