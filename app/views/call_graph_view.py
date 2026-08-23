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
"""Interactive Call Graph, Reference Explorer & Symbol Dependency UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QMenu, QApplication
)

from app.indexer.call_graph import CallGraphEngine


class CallGraphView(QWidget):
    """
    Desktop Call Graph and Reference Explorer tab.
    Visualizes callers, callees, invocations, and dependencies for any symbol.
    """
    jump_requested = pyqtSignal(str, int)  # relative_path, line_number
    create_note_requested = pyqtSignal(str, int, str, str, str, str)  # file, line, symbol, source, title, snippet

    def __init__(self, index_manager=None, parent=None):
        super().__init__(parent)
        self._index_manager = index_manager
        self._current_graph = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Search Bar Row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = QLabel("Symbol Call Graph:", self)
        search_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #1f2328;")
        search_row.addWidget(search_label)

        self.symbol_input = QLineEdit(self)
        self.symbol_input.setObjectName("callGraphSymbolInput")
        self.symbol_input.setPlaceholderText("Enter function, class, method, or struct name to trace call hierarchy...")
        self.symbol_input.returnPressed.connect(self.trace_symbol)
        search_row.addWidget(self.symbol_input, stretch=1)

        self.btn_trace = QPushButton("Trace Hierarchy", self)
        self.btn_trace.setObjectName("callGraphTraceButton")
        self.btn_trace.setStyleSheet("background-color: #0969da; color: #ffffff; font-weight: bold; padding: 5px 12px; border-radius: 4px;")
        self.btn_trace.clicked.connect(self.trace_symbol)
        search_row.addWidget(self.btn_trace)

        layout.addLayout(search_row)

        # 2. Target Symbol Definition Header Card
        self.def_card = QGroupBox("Target Symbol Details", self)
        def_layout = QVBoxLayout(self.def_card)
        def_layout.setContentsMargins(10, 8, 10, 8)
        def_layout.setSpacing(4)

        self.def_title_label = QLabel("No symbol analyzed yet. Enter a symbol name above or select from Search.", self)
        self.def_title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #0969da;")
        def_layout.addWidget(self.def_title_label)

        self.def_meta_label = QLabel("", self)
        self.def_meta_label.setStyleSheet("color: #57606a; font-family: monospace; font-size: 11px;")
        def_layout.addWidget(self.def_meta_label)

        self.btn_open_def = QPushButton("Jump to Definition in Editor", self)
        self.btn_open_def.setStyleSheet("background-color: #2da44e; color: #ffffff; font-weight: 500; font-size: 11px; padding: 4px 10px; border-radius: 4px; max-width: 200px;")
        self.btn_open_def.clicked.connect(self._open_target_def)
        self.btn_open_def.hide()
        def_layout.addWidget(self.btn_open_def)

        layout.addWidget(self.def_card)

        # 3. Main Splitter: Callers (Left) vs Callees & Imports (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: Incoming Callers & References
        callers_box = QGroupBox("Incoming Callers & References (Who calls this?)", splitter)
        callers_layout = QVBoxLayout(callers_box)
        callers_layout.setContentsMargins(8, 8, 8, 8)

        self.callers_table = QTableWidget(0, 4, self)
        self.callers_table.setObjectName("callersTable")
        self.callers_table.setHorizontalHeaderLabels(["Enclosing Scope", "File Path", "Line", "Code Snippet"])
        self.callers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.callers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.callers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.callers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.callers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.callers_table.cellDoubleClicked.connect(self._on_caller_double_clicked)
        self.callers_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.callers_table.customContextMenuRequested.connect(self._on_caller_context_menu)
        callers_layout.addWidget(self.callers_table)

        splitter.addWidget(callers_box)

        # Right: Outgoing Callees & Dependencies
        right_panel = QWidget(splitter)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        callees_box = QGroupBox("Outgoing Callees (What does this function call?)", right_panel)
        callees_box_layout = QVBoxLayout(callees_box)
        callees_box_layout.setContentsMargins(8, 8, 8, 8)

        self.callees_list = QListWidget(self)
        self.callees_list.setObjectName("calleesList")
        self.callees_list.itemDoubleClicked.connect(self._on_callee_double_clicked)
        self.callees_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.callees_list.customContextMenuRequested.connect(self._on_callee_context_menu)
        callees_box_layout.addWidget(self.callees_list)
        right_layout.addWidget(callees_box)

        imports_box = QGroupBox("Module Inclusions & Imports", right_panel)
        imports_box_layout = QVBoxLayout(imports_box)
        imports_box_layout.setContentsMargins(8, 8, 8, 8)

        self.imports_list = QListWidget(self)
        self.imports_list.setObjectName("importsList")
        imports_box_layout.addWidget(self.imports_list)
        right_layout.addWidget(imports_box)

        splitter.addWidget(right_panel)
        splitter.setSizes([600, 450])
        layout.addWidget(splitter, stretch=1)

        # 4. Status Bar
        self.status_label = QLabel("Ready. Type a symbol name to explore its dependency graph.", self)
        self.status_label.setStyleSheet("color: #57606a; font-size: 11px;")
        layout.addWidget(self.status_label)

    def set_index_manager(self, manager) -> None:
        self._index_manager = manager

    def trace_symbol(self, symbol: str | None = None) -> None:
        """Trace call hierarchy for a symbol name."""
        sym_name = symbol if isinstance(symbol, str) and symbol else self.symbol_input.text().strip()
        if not sym_name:
            self.status_label.setText("Please enter a symbol name.")
            return

        self.symbol_input.setText(sym_name)
        repo_root = Path(".")
        symbols = []
        file_corpus = []

        if self._index_manager and self._index_manager.state:
            repo_root = Path(self._index_manager.config.project_root)
            symbols = self._index_manager.state.symbols or []
            file_corpus = self._index_manager.state.file_corpus or []

        self.status_label.setText(f"Analyzing call hierarchy for '{sym_name}'...")
        graph = CallGraphEngine.analyze_symbol(
            repo_root=repo_root,
            symbol_name=sym_name,
            symbols=symbols,
            file_corpus=file_corpus,
        )
        self._current_graph = graph
        self._render_graph(graph)

    def _render_graph(self, graph: dict[str, Any]) -> None:
        sym = graph.get("symbol", "")
        definition = graph.get("definition")
        callers = graph.get("callers", [])
        callees = graph.get("callees", [])
        imports = graph.get("imports", [])

        if definition:
            kind = definition.get("kind", "symbol").upper()
            sig = definition.get("signature") or sym
            path = definition.get("path", "")
            line = definition.get("line", 1)
            doc = definition.get("doc_summary", "")

            self.def_title_label.setText(f"[{kind}] {sig}")
            self.def_meta_label.setText(f"Location: {path}:{line}  |  Doc: {doc or 'No docstring'}")
            self.btn_open_def.show()
        else:
            self.def_title_label.setText(f"Symbol: {sym} (No exact definition found in index)")
            self.def_meta_label.setText("Showing references and call sites across files.")
            self.btn_open_def.hide()

        # Render Callers
        self.callers_table.setRowCount(0)
        for c in callers:
            row = self.callers_table.rowCount()
            self.callers_table.insertRow(row)

            item_scope = QTableWidgetItem(str(c.get("caller", "[global]")))
            item_file = QTableWidgetItem(str(c.get("file", "")))
            item_line = QTableWidgetItem(str(c.get("line", "")))
            item_snip = QTableWidgetItem(str(c.get("snippet", "")))

            item_scope.setData(Qt.ItemDataRole.UserRole, c)
            self.callers_table.setItem(row, 0, item_scope)
            self.callers_table.setItem(row, 1, item_file)
            self.callers_table.setItem(row, 2, item_line)
            self.callers_table.setItem(row, 3, item_snip)

        # Render Callees
        self.callees_list.clear()
        if not callees:
            self.callees_list.addItem("[No outgoing calls identified in body]")
        else:
            for cl in callees:
                name = cl.get("name", "")
                tgt_file = cl.get("target_file")
                tgt_line = cl.get("target_line")
                label = f"➔ {name}()"
                if tgt_file:
                    label += f" ({tgt_file}:{tgt_line})"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, cl)
                self.callees_list.addItem(item)

        # Render Imports
        self.imports_list.clear()
        if not imports:
            self.imports_list.addItem("[No imports identified in module]")
        else:
            for imp in imports:
                self.imports_list.addItem(imp)

        self.status_label.setText(
            f"Analysis complete for '{sym}': {len(callers)} reference(s), {len(callees)} outgoing call(s)."
        )

    def _open_target_def(self) -> None:
        if self._current_graph and self._current_graph.get("definition"):
            d = self._current_graph["definition"]
            self.jump_requested.emit(d.get("path", ""), int(d.get("line") or 1))

    def _on_caller_double_clicked(self, row: int, col: int) -> None:
        item = self.callers_table.item(row, 0)
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get("file"):
                self.jump_requested.emit(data["file"], int(data.get("line") or 1))

    def _on_callee_double_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data.get("name"):
            # Double clicking a callee traces into that callee!
            self.trace_symbol(data["name"])

    def _on_caller_context_menu(self, pos) -> None:
        row = self.callers_table.rowAt(pos.y())
        if row < 0 or row >= self.callers_table.rowCount():
            return
        item = self.callers_table.item(row, 0)
        if not item:
            return

        from app.views.context_menu_builder import ContextMenuBuilder, ItemContext, ContextMenuCallbacks

        data = item.data(Qt.ItemDataRole.UserRole) or {}
        tgt_file = str(data.get("file", ""))
        tgt_line = int(data.get("line") or 1)
        scope = str(data.get("scope", ""))
        snippet = str(data.get("snippet", ""))

        ctx = ItemContext(
            path=tgt_file,
            line=tgt_line,
            symbol=scope,
            source="Call Graph",
            title=f"Note: {scope} ({Path(tgt_file).name}:{tgt_line})",
            snippet=snippet,
        )

        callbacks = ContextMenuCallbacks(
            open_file=lambda p, l: self.jump_requested.emit(p, int(l or 1)),
            create_note=lambda p, l, s, src, t, snip: self.create_note_requested.emit(p, l, s, src, t, snip),
            trace_symbol=self.trace_symbol,
        )

        ContextMenuBuilder.exec_menu(self, self.callers_table.viewport().mapToGlobal(pos), ctx, callbacks)

    def _on_callee_context_menu(self, pos) -> None:
        item = self.callees_list.itemAt(pos)
        if not item:
            return

        from app.views.context_menu_builder import ContextMenuBuilder, ItemContext, ContextMenuCallbacks

        data = item.data(Qt.ItemDataRole.UserRole) or {}
        callee_name = str(data.get("name", ""))
        tgt_file = str(data.get("target_file") or "")
        tgt_line = int(data.get("target_line") or 1)

        ctx = ItemContext(
            path=tgt_file,
            line=tgt_line if tgt_file else None,
            symbol=callee_name,
            source="Call Graph",
            title=f"Note: Callee {callee_name}()",
            can_copy_path=bool(tgt_file),
            can_copy_ref=bool(tgt_file),
        )

        callbacks = ContextMenuCallbacks(
            open_file=lambda p, l: self.jump_requested.emit(p, int(l or 1)) if p else None,
            create_note=lambda p, l, s, src, t, snip: self.create_note_requested.emit(p, l, s, src, t, snip),
            trace_symbol=self.trace_symbol,
        )

        ContextMenuBuilder.exec_menu(self, self.callees_list.viewport().mapToGlobal(pos), ctx, callbacks)


