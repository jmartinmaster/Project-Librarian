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
"""Search browser widget for query input and result browsing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6 import uic
from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl, pyqtSignal, QThread
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.path_controller import PathController
from app.controllers.search_controller import SearchController
from app.indexer.index_manager import IndexManager


class SearchWorker(QThread):
    """Worker thread for background search queries."""

    results_ready = pyqtSignal(list, float, str)

    def __init__(
        self,
        controller: SearchController,
        query: str,
        scope: str,
        limit: int,
        match_case: bool,
        use_regex: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.query = query
        self.scope = scope
        self.limit = limit
        self.match_case = match_case
        self.use_regex = use_regex

    def run(self) -> None:
        import time
        start_time = time.monotonic()
        try:
            results = self.controller.run_search(
                query=self.query,
                scope=self.scope,
                limit=self.limit,
                match_case=self.match_case,
                use_regex=self.use_regex,
            )
        except Exception:
            results = []
        elapsed = time.monotonic() - start_time
        self.results_ready.emit(results, elapsed, self.query)


class SearchView(QWidget):
    """Widget providing near-instant search over in-memory index state."""
    create_note_requested = pyqtSignal(str, int, str, str, str, str)  # file, line, symbol, source, title, snippet

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
        self.stats_label: QLabel
        self._last_results: list[dict[str, object]] = []
        self._active_worker: SearchWorker | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        debounce_ms = getattr(self.index_manager.config, "search_debounce_ms", 300)
        self._search_timer.setInterval(debounce_ms)
        self._search_timer.timeout.connect(self.run_search)
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
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels(["Title", "File", "Path", "Line", "Type", "File Type", "Preview"])
        self.results_table.horizontalHeader().setVisible(True)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(False)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview_pane.setReadOnly(True)

        # Ensure the splitter gives the results table majority space on first show.
        if hasattr(self, "splitter"):
            self.splitter.setSizes([600, 300])

        self.search_button.clicked.connect(self._on_search_triggered)
        self.query_input.returnPressed.connect(self._on_search_triggered)
        self.query_input.textChanged.connect(self._on_query_text_changed)
        self.scope_combo.currentIndexChanged.connect(self.run_search)
        self.query_input.setMaximumWidth(250)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        self.results_table.cellDoubleClicked.connect(self._on_result_double_clicked)
        self.results_table.customContextMenuRequested.connect(self._on_results_context_menu)

        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(10)

        self.match_case = QCheckBox("Match Case", self)
        self.match_case.setObjectName("matchCase")
        self.use_regex = QCheckBox("Use Regex", self)
        self.use_regex.setObjectName("useRegex")
        self.match_case.stateChanged.connect(self.run_search)
        self.use_regex.stateChanged.connect(self.run_search)
        self.changed_only.stateChanged.connect(self.run_search)

        self.stats_label = QLabel("", self)
        self.stats_label.setObjectName("statsLabel")
        self.stats_label.setStyleSheet("color: #a6adc8; font-size: 11px;")

        self.controls_layout.removeWidget(self.changed_only)
        self.controls_layout.addStretch(1)
        options_layout.addWidget(self.changed_only)
        options_layout.addWidget(self.match_case)
        options_layout.addWidget(self.use_regex)
        options_layout.addStretch(1)
        options_layout.addWidget(self.stats_label)

        if self.layout() is not None:
            self.layout().insertLayout(1, options_layout)
            self.layout().setSpacing(6)
            self.layout().setStretch(0, 0)
            self.layout().setStretch(1, 0)
            self.layout().setStretch(2, 1)

    def _on_query_text_changed(self, _text: str) -> None:
        """Trigger a debounced search as the user types."""
        debounce_ms = getattr(self.index_manager.config, "search_debounce_ms", 300)
        self._search_timer.start(debounce_ms)

    def _on_search_triggered(self) -> None:
        """Immediately execute search on Enter or Search button click."""
        self._search_timer.stop()
        self.run_search()

    def wait_for_search(self, timeout_ms: int = 2000) -> None:
        """Wait for active background search worker to finish (useful for testing/synchronization)."""
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.wait(timeout_ms)

    def run_search(self, synchronous: bool = False) -> None:
        """Execute a search over in-memory indexes and populate the table."""
        self._search_timer.stop()
        query = self.query_input.text().strip()
        if not query:
            self._last_results = []
            self.results_table.clearContents()
            self.results_table.setRowCount(0)
            self.preview_pane.setPlainText("Type a query above to search files, symbols, and spreadsheets.")
            self.stats_label.setText("")
            return

        match_case = self.match_case.isChecked() if hasattr(self, "match_case") else False
        use_regex = self.use_regex.isChecked() if hasattr(self, "use_regex") else False
        limit = getattr(self.index_manager.config, "search_result_limit", 100)

        if synchronous:
            import time
            start = time.monotonic()
            results = self._controller.run_search(
                query=query,
                scope=self.scope_combo.currentText(),
                limit=limit,
                match_case=match_case,
                use_regex=use_regex,
            )
            elapsed = time.monotonic() - start
            self._on_search_results_ready(results, elapsed, query)
            return

        # Stop previous background worker if still running
        if self._active_worker is not None and self._active_worker.isRunning():
            try:
                self._active_worker.results_ready.disconnect()
            except Exception:
                pass
            self._active_worker.quit()
            self._active_worker = None

        self.stats_label.setText("Searching...")
        worker = SearchWorker(
            controller=self._controller,
            query=query,
            scope=self.scope_combo.currentText(),
            limit=limit,
            match_case=match_case,
            use_regex=use_regex,
            parent=self,
        )
        worker.results_ready.connect(self._on_search_results_ready)
        self._active_worker = worker
        worker.start()

    def _on_search_results_ready(self, results: list[dict[str, object]], elapsed: float, query: str) -> None:
        """Handle results emitted from background search worker."""
        if self.query_input.text().strip() != query:
            return  # Outdated result

        self._last_results = results
        count = len(results)
        limit = getattr(self.index_manager.config, "search_result_limit", 100)

        if count >= limit:
            self.stats_label.setText(f"Showing top {count} matches ({elapsed:.3f}s)")
        elif count > 0:
            self.stats_label.setText(f"Found {count} match{'es' if count != 1 else ''} ({elapsed:.3f}s)")
        else:
            self.stats_label.setText(f"No matches ({elapsed:.3f}s)")

        self.results_table.setUpdatesEnabled(False)
        try:
            self.results_table.clearContents()
            self.results_table.setRowCount(len(results))
            for row, item in enumerate(results):
                file_name = str(item.get("file") or (Path(str(item.get("path", ""))).name if item.get("path") else ""))
                title = str(item.get("title") or "")
                self.results_table.setItem(row, 0, QTableWidgetItem(title))
                self.results_table.setItem(row, 1, QTableWidgetItem(file_name))
                self.results_table.setItem(row, 2, QTableWidgetItem(str(item.get("path", ""))))
                self.results_table.setItem(row, 3, QTableWidgetItem(str(item.get("line", ""))))
                self.results_table.setItem(row, 4, QTableWidgetItem(str(item.get("type", ""))))
                self.results_table.setItem(row, 5, QTableWidgetItem(str(item.get("file_type", ""))))
                self.results_table.setItem(row, 6, QTableWidgetItem(str(item.get("preview", ""))))
        finally:
            self.results_table.setUpdatesEnabled(True)

        if results:
            self.results_table.selectRow(0)
            self._render_result(results[0])
        else:
            self.preview_pane.setPlainText(f"No results found for '{query}'.")

    def set_query(self, query: str, scope: str | None = None, execute: bool = True, synchronous: bool = True) -> None:
        """Set query/scope from external navigation controls and optionally run."""
        self._search_timer.stop()
        self.query_input.setText(query)
        if scope is not None:
            scope_index = self.scope_combo.findText(scope)
            if scope_index >= 0:
                self.scope_combo.setCurrentIndex(scope_index)
        if execute:
            self.run_search(synchronous=synchronous)

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
        if row < 0 or row >= len(self._last_results):
            return

        from app.views.context_menu_builder import ContextMenuBuilder, ItemContext, ContextMenuCallbacks

        self.results_table.selectRow(row)
        result = self._last_results[row]
        path_text = str(result.get("path", "")).strip()
        line_raw = result.get("line")
        line = int(line_raw) if line_raw is not None and str(line_raw).isdigit() else None
        sym = str(result.get("title", "")).strip() if result.get("type") == "symbol" else ""
        preview = str(result.get("preview", ""))

        ctx = ItemContext(
            path=path_text,
            line=line,
            symbol=sym,
            source="Search Browser",
            title=f"Edit {result.get('title') or Path(path_text).name}",
            snippet=preview,
            extra_actions=[
                ("Export All Results to CSV...", self.export_results_to_csv)
            ] if len(self._last_results) > 0 else [],
        )

        callbacks = ContextMenuCallbacks(
            open_file=lambda p, l: self._open_result_file(result),
            create_note=lambda p, l, s, src, t, snip: self.create_note_requested.emit(p, l, s, src, t, snip),
        )

        ContextMenuBuilder.exec_menu(self, self.results_table.viewport().mapToGlobal(position), ctx, callbacks)

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
