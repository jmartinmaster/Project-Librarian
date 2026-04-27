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

"""Primary desktop window for the standalone Project Librarian app."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, build_about_text
from app.config import save_config
from app.indexer.index_manager import IndexManager
from app.ui.excel_browser import ExcelBrowser
from app.ui.search_browser import SearchBrowser
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Top-level application window with primary tabs."""

    def __init__(self, index_manager: IndexManager) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._tabs: QTabWidget
        self._action_refresh_index: QAction
        self._action_preferences: QAction
        self._settings_menu: QMenu
        self._action_auto_refresh: QAction
        self._help_menu: QMenu
        self._action_about: QAction
        self._auto_refresh_label: QLabel
        self._skipped_label: QLabel
        self._last_refresh_label: QLabel
        self._library_dock: QDockWidget
        self._library_filter_input: QLineEdit
        self._library_tree_toggle: QCheckBox
        self._library_tree: QTreeWidget
        self._status_timer = QTimer(self)
        self._last_applied_refresh_count = -1
        self.search_browser = SearchBrowser(index_manager=self.index_manager)
        self.excel_browser = ExcelBrowser(index_manager=self.index_manager)
        self._load_ui()
        self._build_ui()
        self._build_menu()

    def _load_ui(self) -> None:
        """Load and bind the main window Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "main_window.ui"
        uic.loadUi(ui_path, self)

        tabs = self.findChild(QTabWidget, "tabWidget")
        settings_menu = self.findChild(QMenu, "menuSettings")
        help_menu = self.findChild(QMenu, "menuHelp")
        refresh_action = self.findChild(QAction, "actionRefreshIndex")
        preferences_action = self.findChild(QAction, "actionPreferences")
        about_action = self.findChild(QAction, "actionAbout")
        if any(widget is None for widget in [tabs, settings_menu, help_menu, refresh_action, preferences_action, about_action]):
            raise RuntimeError("Main window UI is missing required widgets/actions.")

        self._tabs = tabs
        self._settings_menu = settings_menu
        self._help_menu = help_menu
        self._action_refresh_index = refresh_action
        self._action_preferences = preferences_action
        self._action_about = about_action

    def _build_ui(self) -> None:
        self._tabs.addTab(self.search_browser, "Search Browser")
        self._tabs.addTab(self.excel_browser, "Excel Library")
        self.setCentralWidget(self._tabs)
        self._build_library_pane()
        self._rebuild_library_tree()

        icon_path = Path(__file__).resolve().parent / "assets" / "library_icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._auto_refresh_label = QLabel("Auto-Refresh: --")
        self._skipped_label = QLabel("Skipped: --")
        self._last_refresh_label = QLabel("Last Refresh: --")
        self.statusBar().addPermanentWidget(self._auto_refresh_label)
        self.statusBar().addPermanentWidget(self._skipped_label)
        self.statusBar().addPermanentWidget(self._last_refresh_label)
        self._status_timer.timeout.connect(self._update_refresh_indicator)
        self._status_timer.start(1000)
        self._update_refresh_indicator()
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        self._action_refresh_index.triggered.connect(self._refresh_index)
        self._action_preferences.triggered.connect(self._open_settings)
        self._action_about.triggered.connect(self._show_about_dialog)

        self._action_auto_refresh = QAction("Auto Refresh Enabled", self)
        self._action_auto_refresh.setCheckable(True)
        self._action_auto_refresh.setChecked(self.index_manager.is_refresh_worker_running())
        self._action_auto_refresh.triggered.connect(self._toggle_auto_refresh)
        self._settings_menu.addSeparator()
        self._settings_menu.addAction(self._action_auto_refresh)

    def _show_about_dialog(self) -> None:
        """Show license and framework attribution required by the packaged app."""
        QMessageBox.about(self, f"About {APP_NAME}", build_about_text())

    def _refresh_index(self) -> None:
        started = self.index_manager.request_refresh_async()
        if started:
            self.statusBar().showMessage("Refreshing index in background...")
        else:
            self.statusBar().showMessage("Refresh already in progress.")
        self._update_refresh_indicator()

    def _build_library_pane(self) -> None:
        """Build a browse-first navigation pane that mirrors indexed library content."""
        self._library_dock = QDockWidget("Indexed Library", self)
        self._library_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        container = QWidget(self._library_dock)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._library_filter_input = QLineEdit(container)
        self._library_filter_input.setObjectName("libraryFilterInput")
        self._library_filter_input.setPlaceholderText("Filter indexed library...")
        self._library_filter_input.textChanged.connect(self._rebuild_library_tree)
        layout.addWidget(self._library_filter_input)

        self._library_tree_toggle = QCheckBox("Tree View", container)
        self._library_tree_toggle.setObjectName("libraryTreeToggle")
        self._library_tree_toggle.setChecked(True)
        self._library_tree_toggle.toggled.connect(self._rebuild_library_tree)
        layout.addWidget(self._library_tree_toggle)

        self._library_tree = QTreeWidget(self._library_dock)
        self._library_tree.setObjectName("libraryTree")
        self._library_tree.setColumnCount(2)
        self._library_tree.setHeaderLabels(["Library", "Location"])
        self._library_tree.itemActivated.connect(self._on_library_item_activated)
        self._library_tree.itemDoubleClicked.connect(self._on_library_item_double_clicked)
        self._library_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._library_tree.customContextMenuRequested.connect(self._on_library_context_menu)
        layout.addWidget(self._library_tree)
        self._library_dock.setWidget(container)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._library_dock)

    def _rebuild_library_tree(self) -> None:
        """Render current index state into the library navigation tree."""
        state = self.index_manager.state
        tree = self._library_tree
        filter_text = self._library_filter_input.text().strip().lower() if hasattr(self, "_library_filter_input") else ""
        tree_mode = self._library_tree_toggle.isChecked() if hasattr(self, "_library_tree_toggle") else True
        tree.setUpdatesEnabled(False)
        tree.clear()

        sorted_files = sorted(state.file_corpus.keys())
        matching_files = [
            rel_path
            for rel_path in sorted_files
            if not filter_text or filter_text in rel_path.lower() or filter_text in Path(rel_path).name.lower()
        ]

        files_label = (
            f"Files ({len(matching_files)}/{len(state.file_corpus)})"
            if filter_text
            else f"Files ({len(state.file_corpus)})"
        )
        files_root = QTreeWidgetItem([files_label, ""])
        tree.addTopLevelItem(files_root)
        file_limit = 400
        visible_files = matching_files[:file_limit]
        if tree_mode:
            folder_nodes: dict[tuple[str, ...], QTreeWidgetItem] = {}
            for rel_path in visible_files:
                parts = Path(rel_path).parts
                for depth in range(1, len(parts)):
                    prefix = tuple(parts[:depth])
                    if prefix in folder_nodes:
                        continue
                    parent_prefix = prefix[:-1]
                    parent_item = folder_nodes.get(parent_prefix, files_root)
                    folder_item = QTreeWidgetItem([parts[depth - 1], "/".join(prefix)])
                    parent_item.addChild(folder_item)
                    folder_nodes[prefix] = folder_item

                parent_prefix = tuple(parts[:-1])
                parent_item = folder_nodes.get(parent_prefix, files_root)
                item = QTreeWidgetItem([parts[-1], rel_path])
                item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "file", "path": rel_path})
                parent_item.addChild(item)
        else:
            for rel_path in visible_files:
                item = QTreeWidgetItem([Path(rel_path).name, rel_path])
                item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "file", "path": rel_path})
                files_root.addChild(item)

        if len(matching_files) > file_limit:
            files_root.addChild(QTreeWidgetItem([f"... {len(matching_files) - file_limit} more", ""]))

        matching_symbols = [
            symbol
            for symbol in state.symbols
            if not filter_text
            or filter_text in str(symbol.get("name", "")).lower()
            or filter_text in str(symbol.get("path", "")).lower()
            or filter_text in str(symbol.get("kind", "")).lower()
        ]
        symbols_label = (
            f"Symbols ({len(matching_symbols)}/{len(state.symbols)})"
            if filter_text
            else f"Symbols ({len(state.symbols)})"
        )
        symbols_root = QTreeWidgetItem([symbols_label, ""])
        tree.addTopLevelItem(symbols_root)
        symbol_limit = 600
        for symbol in matching_symbols[:symbol_limit]:
            name = str(symbol.get("name", "<unknown>"))
            kind = str(symbol.get("kind", "symbol"))
            path = str(symbol.get("path", ""))
            line = str(symbol.get("line", ""))
            item = QTreeWidgetItem([f"{name} [{kind}]", f"{path}:{line}"])
            item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "symbol", "name": name, "path": path, "line": line})
            symbols_root.addChild(item)
        if len(matching_symbols) > symbol_limit:
            symbols_root.addChild(QTreeWidgetItem([f"... {len(matching_symbols) - symbol_limit} more", ""]))

        matching_excel_rows = [
            row
            for row in state.excel_rows
            if not filter_text
            or filter_text in str(row.get("file", "")).lower()
            or filter_text in str(row.get("field", "")).lower()
            or filter_text in str(row.get("value", "")).lower()
        ]
        excel_label = (
            f"Excel Rows ({len(matching_excel_rows)}/{len(state.excel_rows)})"
            if filter_text
            else f"Excel Rows ({len(state.excel_rows)})"
        )
        excel_root = QTreeWidgetItem([excel_label, ""])
        tree.addTopLevelItem(excel_root)
        excel_limit = 400
        for row in matching_excel_rows[:excel_limit]:
            field = str(row.get("field", ""))
            value = str(row.get("value", ""))
            file_name = str(row.get("file", ""))
            item = QTreeWidgetItem([field or "<field>", file_name])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"kind": "excel", "query": value, "path": file_name, "line": str(row.get("row", ""))},
            )
            excel_root.addChild(item)
        if len(matching_excel_rows) > excel_limit:
            excel_root.addChild(QTreeWidgetItem([f"... {len(matching_excel_rows) - excel_limit} more", ""]))

        all_skipped_files = state.skipped_files
        matching_skipped_files = [
            item
            for item in all_skipped_files
            if not filter_text
            or filter_text in str(item.get("path", "")).lower()
            or filter_text in str(item.get("reason", "")).lower()
            or filter_text in str(item.get("stage", "")).lower()
        ]
        skipped_label = (
            f"Skipped Files ({len(matching_skipped_files)}/{len(all_skipped_files)})"
            if filter_text
            else f"Skipped Files ({len(all_skipped_files)})"
        )
        skipped_root = QTreeWidgetItem([skipped_label, ""])
        tree.addTopLevelItem(skipped_root)
        skipped_limit = 400
        for skipped in matching_skipped_files[:skipped_limit]:
            path_text = str(skipped.get("path", ""))
            stage_text = str(skipped.get("stage", ""))
            reason_text = str(skipped.get("reason", ""))
            item = QTreeWidgetItem([Path(path_text).name or path_text, f"{stage_text}: {reason_text}"])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"kind": "skipped", "path": path_text, "reason": reason_text, "stage": stage_text},
            )
            skipped_root.addChild(item)
        if len(matching_skipped_files) > skipped_limit:
            skipped_root.addChild(QTreeWidgetItem([f"... {len(matching_skipped_files) - skipped_limit} more", ""]))

        for idx in range(tree.topLevelItemCount()):
            tree.topLevelItem(idx).setExpanded(True)
        tree.setUpdatesEnabled(True)

    def _on_library_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        """Route library navigation actions to the appropriate browse view."""
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return

        kind = str(payload.get("kind", ""))
        if kind == "file":
            self._tabs.setCurrentWidget(self.search_browser)
            self.search_browser.set_query(query=str(payload.get("path", "")), scope="files", execute=True)
            return

        if kind == "symbol":
            self._tabs.setCurrentWidget(self.search_browser)
            self.search_browser.set_query(query=str(payload.get("name", "")), scope="symbols", execute=True)
            return

        if kind == "excel":
            self._tabs.setCurrentWidget(self.excel_browser)
            self.excel_browser.set_filter(query=str(payload.get("query", "")), execute=True)

        if kind == "skipped":
            self.statusBar().showMessage(
                f"Skipped file: {payload.get('path', '')} ({payload.get('stage', '')}: {payload.get('reason', '')})"
            )

    def _on_library_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Open underlying file when a library item is double clicked."""
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        path_text = self._payload_path(payload)
        self._open_path(path_text)

    def _on_library_context_menu(self, position: QPoint) -> None:
        """Show context menu with open/copy actions for selected library item."""
        item = self._library_tree.itemAt(position)
        if item is None:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        path_text = self._payload_path(payload)
        reference = self._payload_reference(payload)

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

        selected = menu.exec(self._library_tree.viewport().mapToGlobal(position))
        if selected is None:
            return
        if selected == open_action:
            self._open_path(path_text)
            return
        if selected == copy_path_action and path_text:
            QApplication.clipboard().setText(path_text)
            return
        if selected == copy_reference_action and reference:
            QApplication.clipboard().setText(reference)

    def _payload_path(self, payload: object) -> str:
        """Extract a best-effort path from tree payload metadata."""
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("path", "")).strip()

    def _payload_reference(self, payload: object) -> str:
        """Extract path:line-style reference from tree payload metadata."""
        if not isinstance(payload, dict):
            return ""
        path_text = str(payload.get("path", "")).strip()
        line_text = str(payload.get("line", "")).strip()
        if path_text and line_text:
            return f"{path_text}:{line_text}"
        return path_text

    def _open_path(self, path_text: str) -> None:
        """Open a file path in the desktop shell if it exists."""
        resolved = self._resolve_path(path_text)
        if resolved is None or not resolved.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))

    def _resolve_path(self, path_text: str) -> Path | None:
        """Resolve relative index path against configured project root."""
        if not path_text:
            return None
        candidate = Path(path_text)
        if candidate.is_absolute():
            return candidate
        repo_root = Path(self.index_manager.config.project_root or Path.cwd())
        return (repo_root / candidate).resolve()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.index_manager.config, self)
        if dialog.exec():
            save_config(self.index_manager.config)
            self.index_manager.start_refresh_worker(force_restart=True)
            self._action_auto_refresh.setChecked(self.index_manager.is_refresh_worker_running())
            self._refresh_index()

    def _toggle_auto_refresh(self, enabled: bool) -> None:
        """Enable or disable interval-based auto-refresh worker."""
        if enabled:
            self.index_manager.start_refresh_worker(force_restart=True)
        else:
            self.index_manager.stop_refresh_worker()
        self._action_auto_refresh.setChecked(self.index_manager.is_refresh_worker_running())
        self._update_refresh_indicator()

    def _update_refresh_indicator(self) -> None:
        """Refresh status-bar labels for worker state and last refresh time."""
        status = self.index_manager.refresh_status()
        refresh_count = int(status.get("refresh_count") or 0)
        worker_running = bool(status.get("worker_running"))
        refresh_in_progress = bool(status.get("refresh_in_progress"))
        interval = float(status.get("interval_seconds") or 0.0)
        last_refresh = status.get("last_refresh_at") or "--"
        skipped_count = int(status.get("skipped_count") or 0)
        worker_text = "running" if worker_running else "stopped"

        if refresh_count != self._last_applied_refresh_count:
            self._rebuild_library_tree()
            self._last_applied_refresh_count = refresh_count
            summary = self.index_manager.state
            self.statusBar().showMessage(
                "Refreshed: "
                f"files={len(summary.file_corpus)} symbols={len(summary.symbols)} "
                f"excel_rows={len(summary.excel_rows)} skipped={len(summary.skipped_files)}"
            )

        if refresh_in_progress:
            worker_text = f"{worker_text}, indexing"

        self._auto_refresh_label.setText(f"Auto-Refresh: {worker_text} ({interval:.1f}s)")
        self._skipped_label.setText(f"Skipped: {skipped_count}")
        self._last_refresh_label.setText(f"Last Refresh: {last_refresh}")
        if hasattr(self, "_action_auto_refresh"):
            self._action_auto_refresh.setChecked(worker_running)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop background workers before window teardown."""
        self._status_timer.stop()
        self.index_manager.stop_refresh_worker()
        super().closeEvent(event)
