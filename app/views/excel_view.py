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
"""Excel browser widget for quick keyword row inspection."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.controllers.excel_controller import ExcelController
from app.indexer.index_manager import IndexManager


class ExcelView(QWidget):
    """Browser widget for indexed Excel workbook contents."""
    create_note_requested = pyqtSignal(str, int, str, str, str, str)  # file, line, symbol, source, title, snippet

    def __init__(
        self,
        index_manager: IndexManager,
        controller: ExcelController | None = None,
    ) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._controller = controller or ExcelController(index_manager=index_manager)
        self._last_rows: list[dict[str, object]] = []
        self.query_input: QLineEdit
        self.filter_button: QPushButton
        self.results_table: QTableWidget
        self._load_ui()
        self._build_ui()

    def _load_ui(self) -> None:
        """Load and bind the excel browser Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "excel_view.ui"
        uic.loadUi(ui_path, self)

        query_input = self.findChild(QLineEdit, "queryInput")
        filter_button = self.findChild(QPushButton, "filterButton")
        results_table = self.findChild(QTableWidget, "resultsTable")
        if query_input is None or filter_button is None or results_table is None:
            raise RuntimeError("Excel browser UI is missing required widgets.")

        self.query_input = query_input
        self.filter_button = filter_button
        self.results_table = results_table

    def _build_ui(self) -> None:
        self.results_table.setHorizontalHeaderLabels(["File", "Sheet", "Row", "Field", "Value"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._on_context_menu)

        self.query_input.setMaximumWidth(250)
        from PyQt6.QtWidgets import QHBoxLayout
        controls_layout = self.findChild(QHBoxLayout, "controlsLayout")
        if controls_layout is not None:
            controls_layout.addStretch(1)

        self.filter_button.clicked.connect(self.run_filter)
        self.query_input.returnPressed.connect(self.run_filter)

    def run_filter(self) -> None:
        """Filter loaded Excel rows currently stored in memory."""
        self._last_rows = self._controller.filter_rows(self.query_input.text())
        rows = self._last_rows

        self.results_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            self.results_table.setItem(row_index, 0, QTableWidgetItem(str(item.get("file", ""))))
            self.results_table.setItem(row_index, 1, QTableWidgetItem(str(item.get("sheet", ""))))
            self.results_table.setItem(row_index, 2, QTableWidgetItem(str(item.get("row", ""))))
            self.results_table.setItem(row_index, 3, QTableWidgetItem(str(item.get("field", ""))))
            self.results_table.setItem(row_index, 4, QTableWidgetItem(str(item.get("value", ""))))

    def _on_context_menu(self, position: QPoint) -> None:
        row = self.results_table.rowAt(position.y())
        if row < 0 or row >= len(self._last_rows):
            return

        from app.views.context_menu_builder import ContextMenuBuilder, ItemContext, ContextMenuCallbacks

        item = self._last_rows[row]
        tgt_file = str(item.get("file", ""))
        row_num = int(item.get("row", 1)) if str(item.get("row", "")).isdigit() else 1
        sheet = str(item.get("sheet", ""))
        field = str(item.get("field", ""))
        val = str(item.get("value", ""))
        snippet = f"Sheet: {sheet}\nField: {field}\nValue: {val}"

        ctx = ItemContext(
            path=tgt_file,
            line=row_num,
            symbol=field,
            source="Excel Library",
            title=f"Note: {Path(tgt_file).name} ({sheet} - Row {row_num})",
            snippet=snippet,
            can_open=False,
            extra_actions=[
                ("Copy Value", lambda: QApplication.clipboard().setText(val))
            ],
        )

        callbacks = ContextMenuCallbacks(
            create_note=lambda p, l, s, src, t, snip: self.create_note_requested.emit(p, l, s, src, t, snip),
        )

        ContextMenuBuilder.exec_menu(self, self.results_table.viewport().mapToGlobal(position), ctx, callbacks)


    def set_filter(self, query: str, execute: bool = True) -> None:
        """Set filter query from external navigation controls and optionally run."""
        self.query_input.setText(query)
        if execute:
            self.run_filter()
