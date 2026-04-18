"""Excel browser widget for quick keyword row inspection."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtWidgets import (
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.indexer.index_manager import IndexManager


class ExcelBrowser(QWidget):
    """Widget for filtering in-memory Excel keyword row records."""

    def __init__(self, index_manager: IndexManager) -> None:
        super().__init__()
        self.index_manager = index_manager
        self.query_input: QLineEdit
        self.filter_button: QPushButton
        self.results_table: QTableWidget
        self._load_ui()
        self._build_ui()

    def _load_ui(self) -> None:
        """Load and bind the excel browser Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "excel_browser.ui"
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

        self.filter_button.clicked.connect(self.run_filter)
        self.query_input.returnPressed.connect(self.run_filter)

    def run_filter(self) -> None:
        """Filter loaded Excel rows currently stored in memory."""
        needle = self.query_input.text().strip().lower()
        rows = self.index_manager.state.excel_rows
        if needle:
            rows = [
                item
                for item in rows
                if needle in " ".join(
                    [str(item.get("file", "")), str(item.get("field", "")), str(item.get("value", ""))]
                ).lower()
            ]

        self.results_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            self.results_table.setItem(row_index, 0, QTableWidgetItem(str(item.get("file", ""))))
            self.results_table.setItem(row_index, 1, QTableWidgetItem(str(item.get("sheet", ""))))
            self.results_table.setItem(row_index, 2, QTableWidgetItem(str(item.get("row", ""))))
            self.results_table.setItem(row_index, 3, QTableWidgetItem(str(item.get("field", ""))))
            self.results_table.setItem(row_index, 4, QTableWidgetItem(str(item.get("value", ""))))

    def set_filter(self, query: str, execute: bool = True) -> None:
        """Set filter query from external navigation controls and optionally run."""
        self.query_input.setText(query)
        if execute:
            self.run_filter()
