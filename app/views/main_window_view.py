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
"""Primary desktop window for the standalone The Librarian app."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from app import APP_NAME, build_about_text
from app.controllers.main_window_controller import MainWindowViewController
from app.controllers.path_controller import PathController
from app.indexer.index_manager import IndexManager
from app.views.excel_view import ExcelView
from app.views.search_view import SearchView
from app.views.settings_view import SettingsView
from app.views.anti_pattern_view import AntiPatternView
from app.views.diagnostics_view import DiagnosticsView
from app.views.call_graph_view import CallGraphView
from app.views.notes_view import NotesView
from app.views.mvc_editor_tab import MVCEditorTab
from app.views.workspace_view import WorkspaceView
from app.views.integrations_view import IntegrationsView
from app.models.mcp_server_manager import MCPServerManager


class LibraryDockTitleBar(QWidget):
    """Custom title bar for the Indexed Library dock widget to allow collapsing."""

    def __init__(self, dock_widget: QDockWidget, content_widget: QWidget) -> None:
        super().__init__(dock_widget)
        self.dock_widget = dock_widget
        self.content_widget = content_widget
        self.collapsed = False

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)

        self.title_label = QLabel("Indexed Library", self)
        self.title_label.setStyleSheet("font-weight: bold; color: #cdd6f4;")

        self.collapse_btn = QPushButton("◀", self)
        self.collapse_btn.setFixedSize(30, 30)
        self.collapse_btn.setToolTip("Collapse Sidebar")
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #a6adc8;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #f38ba8;
                border-radius: 3px;
            }
        """)

        self.float_btn = QPushButton("❐", self)
        self.float_btn.setFixedSize(30, 30)
        self.float_btn.setToolTip("Pop out")
        self.float_btn.setStyleSheet(self.collapse_btn.styleSheet())

        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setToolTip("Close")
        self.close_btn.setStyleSheet(self.collapse_btn.styleSheet())

        self.layout.addWidget(self.title_label)
        self.layout.addStretch()
        self.layout.addWidget(self.collapse_btn)
        self.layout.addWidget(self.float_btn)
        self.layout.addWidget(self.close_btn)

        self.collapse_btn.clicked.connect(self.toggle_collapse)
        self.float_btn.clicked.connect(self.toggle_float)
        self.close_btn.clicked.connect(self.dock_widget.close)

        self.dock_widget.topLevelChanged.connect(self._on_top_level_changed)

    def toggle_collapse(self) -> None:
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.content_widget.setVisible(False)
            self.title_label.setVisible(False)
            self.float_btn.setVisible(False)
            self.close_btn.setVisible(False)
            self.collapse_btn.setText("▶")
            self.collapse_btn.setToolTip("Expand Sidebar")
            self.dock_widget.setMinimumWidth(32)
            self.dock_widget.setMaximumWidth(32)
        else:
            self.content_widget.setVisible(True)
            self.title_label.setVisible(True)
            self.float_btn.setVisible(True)
            self.close_btn.setVisible(True)
            self.collapse_btn.setText("◀")
            self.collapse_btn.setToolTip("Collapse Sidebar")
            self.dock_widget.setMinimumWidth(500)
            self.dock_widget.setMaximumWidth(1900)

    def toggle_float(self) -> None:
        self.dock_widget.setFloating(not self.dock_widget.isFloating())

    def _on_top_level_changed(self, floating: bool) -> None:
        if floating and self.collapsed:
            self.toggle_collapse()


class MainWindowView(QMainWindow):
    """Top-level application window with primary tabs."""

    def __init__(
        self,
        index_manager: IndexManager,
        controller: MainWindowViewController | None = None,
        path_controller: PathController | None = None,
    ) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._controller = controller or MainWindowViewController(index_manager=index_manager)
        self._path_controller = path_controller or PathController(index_manager=index_manager)
        self._tabs: QTabWidget
        self._action_refresh_index: QAction
        self._action_preferences: QAction
        self._settings_menu: QMenu
        self._action_auto_refresh: QAction
        self._help_menu: QMenu
        self._action_about: QAction
        self._progress_bar: QProgressBar
        self._ram_label: QLabel
        self._auto_refresh_label: QLabel
        self._skipped_label: QLabel
        self._last_refresh_label: QLabel
        self._library_dock: QDockWidget
        self._library_filter_input: QLineEdit
        self._library_tree_toggle: QCheckBox
        self._library_tree: QTreeWidget
        self._status_timer = QTimer(self)
        self._last_applied_refresh_count = -1
        self._last_reported_refresh_error = ""
        self.mcp_server_manager = MCPServerManager(index_manager=self.index_manager)
        self.search_view = SearchView(
            index_manager=self.index_manager,
            open_file_callback=self._open_in_mvc_editor,
        )
        self.excel_view = ExcelView(index_manager=self.index_manager)
        self.anti_pattern_view = AntiPatternView(
            index_manager=self.index_manager,
            open_file_callback=self._open_in_mvc_editor,
        )
        self.diagnostics_view = DiagnosticsView(index_manager=self.index_manager)
        self.call_graph_view = CallGraphView(index_manager=self.index_manager)
        self.call_graph_view.jump_requested.connect(self._open_in_mvc_editor)
        self.notes_view = NotesView(project_root=self.index_manager.config.project_root, parent=self)
        self.notes_view.jump_requested.connect(self._open_in_mvc_editor)
        self.mvc_editor_tab = MVCEditorTab(
            workspace_root=self.index_manager.config.project_root,
            index_manager=self.index_manager,
        )
        self.workspace_view = WorkspaceView(index_manager=self.index_manager)
        self.integrations_view = IntegrationsView(
            config=self.index_manager.config,
            mcp_manager=self.mcp_server_manager,
            on_project_root_changed=self._on_project_root_changed,
        )

        # Wire right-click note creation across all indexed browse views
        self.search_view.create_note_requested.connect(self._on_subview_create_note)
        self.excel_view.create_note_requested.connect(self._on_subview_create_note)
        self.anti_pattern_view.create_note_requested.connect(self._on_subview_create_note)
        self.call_graph_view.create_note_requested.connect(self._on_subview_create_note)
        self.mvc_editor_tab.create_note_requested.connect(self._on_subview_create_note)

        self._load_ui()
        self._build_ui()
        self._build_menu()

    def _load_ui(self) -> None:
        """Load and bind the main window Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "main_window_view.ui"
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
        self._tabs.addTab(self.search_view, "Search Browser")
        self._tabs.addTab(self.excel_view, "Excel Library")
        self._tabs.addTab(self.anti_pattern_view, "Code Audit")
        self._tabs.addTab(self.diagnostics_view, "Diagnostics")
        self._tabs.addTab(self.call_graph_view, "Call Graph")
        self._tabs.addTab(self.notes_view, "Notes")
        self._tabs.addTab(self.mvc_editor_tab, "Editor")
        self._tabs.addTab(self.workspace_view, "Workspace Tools")
        self._tabs.addTab(self.integrations_view, "Integrations")
        self.setCentralWidget(self._tabs)
        self._build_library_pane()

        self.setStyleSheet("""
            QMainWindow::separator {
                background-color: #313244;
                width: 8px;
                height: 8px;
            }
            QMainWindow::separator:hover {
                background-color: #89b4fa;
            }
        """)
        self._rebuild_library_tree()
        if self.index_manager.config.mcp_autostart:
            self.mcp_server_manager.start()
            self.integrations_view.refresh_status("Auto-start enabled")

        icon_path = Path(__file__).resolve().parent / "assets" / "library_icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setFixedWidth(160)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #45475a;
                border-radius: 4px;
                background-color: #1e1e2e;
                text-align: center;
                color: #cdd6f4;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 3px;
            }
        """)
        self._progress_bar.hide()

        self._ram_label = QLabel("RAM: --")
        self._ram_label.setStyleSheet("padding: 0 4px;")
        self._auto_refresh_label = QLabel("Auto-Refresh: --")
        self._skipped_label = QLabel("Skipped: --")
        self._last_refresh_label = QLabel("Last Refresh: --")
        self.statusBar().addPermanentWidget(self._progress_bar)
        self.statusBar().addPermanentWidget(self._ram_label)
        self.statusBar().addPermanentWidget(self._auto_refresh_label)
        self.statusBar().addPermanentWidget(self._skipped_label)
        self.statusBar().addPermanentWidget(self._last_refresh_label)
        self._status_timer.timeout.connect(self._update_refresh_indicator)
        self._status_timer.start(500)
        self._update_refresh_indicator()
        self.statusBar().showMessage("Ready")

        # Set dock to ~25% of screen width once the window geometry is known.
        screen = QApplication.primaryScreen()
        if screen:
            dock_width = max(420, screen.geometry().width() // 4)
            self.resizeDocks([self._library_dock], [dock_width], Qt.Orientation.Horizontal)

    def _build_menu(self) -> None:
        self._action_refresh_index.triggered.connect(self._refresh_index)
        self._action_preferences.triggered.connect(self._open_settings)
        self._action_about.triggered.connect(self._show_about_dialog)

        # Wire and insert Help Content action dynamically before About action
        self._action_help_content = QAction("Librarian User Guide", self)
        self._action_help_content.setShortcut("F1")
        self._action_help_content.triggered.connect(self._show_help_dialog)
        self._help_menu.insertAction(self._action_about, self._action_help_content)
        self._help_menu.insertSeparator(self._action_about)

        # Get or setup File menu programmatically
        file_menu = self.findChild(QMenu, "menuFile")
        if file_menu is not None:
            file_menu.clear()
            
            # 1. Open Workspace...
            self._action_open_workspace = QAction("Open Workspace...", self)
            self._action_open_workspace.setShortcut("Ctrl+O")
            self._action_open_workspace.triggered.connect(self._open_workspace_dialog)
            file_menu.addAction(self._action_open_workspace)

            # 2. Recent Projects
            self._recent_menu = file_menu.addMenu("Open Recent Project")
            self._populate_recent_projects_menu()

            # 3. Save Files
            self._action_save_files = QAction("Save Files", self)
            self._action_save_files.setShortcut("Ctrl+S")
            self._action_save_files.triggered.connect(self._save_files)
            file_menu.addAction(self._action_save_files)

            file_menu.addSeparator()

            # 4. Refresh Index
            file_menu.addAction(self._action_refresh_index)
            
            file_menu.addSeparator()
            
            # 4. Close
            self._action_close = QAction("Close", self)
            self._action_close.setShortcut("Alt+F4")
            self._action_close.triggered.connect(self.close)
            file_menu.addAction(self._action_close)

        self._action_auto_refresh = QAction("Auto Refresh Enabled", self)
        self._action_auto_refresh.setCheckable(True)
        self._action_auto_refresh.setChecked(self.index_manager.is_refresh_worker_running())
        self._action_auto_refresh.triggered.connect(self._toggle_auto_refresh)
        self._settings_menu.addSeparator()
        self._settings_menu.addAction(self._action_auto_refresh)

        # Build View menu with Sidebar toggle and tab shortcuts
        view_menu = self.findChild(QMenu, "menuView")
        if view_menu is None:
            view_menu = QMenu("View", self)
            self.menuBar().insertMenu(self._settings_menu.menuAction(), view_menu)

        view_menu.clear()

        # 1. Toggle Library Sidebar (Ctrl+B)
        self._action_toggle_sidebar = QAction("Show Indexed Library Sidebar", self)
        self._action_toggle_sidebar.setShortcut("Ctrl+B")
        self._action_toggle_sidebar.setCheckable(True)
        self._action_toggle_sidebar.setChecked(not self._library_dock.isHidden())
        self._action_toggle_sidebar.triggered.connect(self._toggle_library_dock)
        view_menu.addAction(self._action_toggle_sidebar)
        self._library_dock.visibilityChanged.connect(self._action_toggle_sidebar.setChecked)

        view_menu.addSeparator()

        # 2. Tab Navigation Actions (Ctrl+1 .. Ctrl+9)
        for idx in range(self._tabs.count()):
            t_name = self._tabs.tabText(idx)
            t_act = QAction(f"Show {t_name}", self)
            if idx < 9:
                t_act.setShortcut(f"Ctrl+{idx+1}")
            t_act.triggered.connect(lambda checked, i=idx: self._tabs.setCurrentIndex(i))
            view_menu.addAction(t_act)

    def _toggle_library_dock(self, checked: bool) -> None:
        """Show or hide the Indexed Library sidebar dock."""
        if checked:
            self._library_dock.show()
            self._library_dock.raise_()
        else:
            self._library_dock.hide()

    def _open_workspace_dialog(self) -> None:
        """Prompt user for a folder to set as the active project root workspace."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Workspace Folder",
            self.index_manager.config.project_root or "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        if not self._confirm_workspace_load(path):
            self.statusBar().showMessage("Workspace load cancelled.", 3000)
            return

        self.index_manager.config.project_root = path
        self.index_manager.config.mvc_editor_root = path
        from app.config import save_config
        save_config(self.index_manager.config)

        self._on_project_root_changed(path)
        self.integrations_view.sync_from_config()
        self._refresh_index()

    def _confirm_workspace_load(self, path: str) -> bool:
        """Show live scan progress, then the estimated RAM cost, and ask to proceed."""
        from app.views.scan_progress_view import WorkspaceScanProgressDialog

        progress_dialog = WorkspaceScanProgressDialog(self._controller, path, self)
        progress_dialog.exec()

        if progress_dialog.was_cancelled() or progress_dialog.result_estimate() is None:
            return False

        estimate = progress_dialog.result_estimate()
        message = (
            f"Scanned folder: {path}\n\n"
            f"Indexable files: {estimate.file_count}\n"
            f"On-disk size: {estimate.total_size_text}\n"
            f"Estimated RAM required to load: {estimate.estimated_ram_text}\n"
        )
        if estimate.skipped_large_count:
            message += f"Files skipped (too large): {estimate.skipped_large_count}\n"
        message += "\nContinue loading this workspace?"

        choice = QMessageBox.question(
            self,
            "Confirm Workspace Load",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        return choice == QMessageBox.StandardButton.Yes

    def _save_files(self) -> None:
        """Trigger save on the embedded MVC editor tab."""
        self.mvc_editor_tab.save_current_file()
        self.statusBar().showMessage("Saved open MVC files.", 3000)

    def _show_about_dialog(self) -> None:
        """Show license and framework attribution required by the packaged app."""
        QMessageBox.about(self, f"About {APP_NAME}", build_about_text())

    def _show_help_dialog(self) -> None:
        """Show the premium in-app Help Dialog containing the User Guide."""
        from app.views.help_view import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec()

    def _refresh_index(self) -> None:
        started = self._controller.request_refresh()
        if started:
            self.statusBar().showMessage("Refreshing index in background...")
        else:
            status = self._controller.refresh_status()
            running_seconds = status.get("refresh_running_seconds")
            if running_seconds is not None:
                self.statusBar().showMessage(
                    f"Refresh already in progress (running for {int(running_seconds)}s)."
                )
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
        self._library_tree.header().setStretchLastSection(False)

        def tree_resize_event(event):
            QTreeWidget.resizeEvent(self._library_tree, event)
            w = self._library_tree.viewport().width()
            self._library_tree.setColumnWidth(0, max(50, int(w * 0.66)))
            self._library_tree.setColumnWidth(1, max(25, int(w * 0.34)))

        self._library_tree.resizeEvent = tree_resize_event

        self._library_tree.itemActivated.connect(self._on_library_item_activated)
        self._library_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._library_tree.customContextMenuRequested.connect(self._on_library_context_menu)
        self._library_tree.setMinimumWidth(50)
        self._library_filter_input.setMinimumWidth(50)
        self._library_dock.setMinimumWidth(50)

        layout.addWidget(self._library_tree)
        self._library_dock.setWidget(container)

        title_bar = LibraryDockTitleBar(self._library_dock, container)
        self._library_dock.setTitleBarWidget(title_bar)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._library_dock)

    def _rebuild_library_tree(self) -> None:
        """Render current index state into the library navigation tree."""
        tree = self._library_tree
        filter_text = self._library_filter_input.text().strip().lower() if hasattr(self, "_library_filter_input") else ""
        tree_mode = self._library_tree_toggle.isChecked() if hasattr(self, "_library_tree_toggle") else True
        tree.setUpdatesEnabled(False)
        tree.clear()

        matching_files, total_files = self._controller.matching_files(filter_text)

        files_label = (
            f"Files ({len(matching_files)}/{total_files})"
            if filter_text
            else f"Files ({total_files})"
        )
        files_root = QTreeWidgetItem([files_label, ""])
        tree.addTopLevelItem(files_root)
        if tree_mode:
            from collections import defaultdict
            # Group items by parent folder prefix
            children_map = defaultdict(lambda: {"folders": set(), "files": []})
            for rel_path in matching_files:
                parts = Path(rel_path).parts
                for depth in range(1, len(parts)):
                    parent_prefix = tuple(parts[:depth-1])
                    folder_name = parts[depth-1]
                    children_map[parent_prefix]["folders"].add(folder_name)
                parent_prefix = tuple(parts[:-1])
                file_name = parts[-1]
                children_map[parent_prefix]["files"].append((file_name, rel_path))

            # Populating tree using a queue for BFS traversal of parent prefixes
            queue = [((), files_root)]
            folder_items = {(): files_root}
            folder_limit = 200 # limit of children (folders + files) per folder node

            while queue:
                prefix, parent_item = queue.pop(0)
                data = children_map.get(prefix)
                if not data:
                    continue

                sorted_folders = sorted(list(data["folders"]))
                sorted_files = sorted(data["files"], key=lambda x: x[0])
                total_children = len(sorted_folders) + len(sorted_files)

                # Determine visible children based on limit
                visible_folders = []
                visible_files = []
                if len(sorted_folders) >= folder_limit:
                    visible_folders = sorted_folders[:folder_limit]
                else:
                    visible_folders = sorted_folders
                    visible_files = sorted_files[:folder_limit - len(visible_folders)]

                # Add visible folders
                for folder_name in visible_folders:
                    folder_prefix = prefix + (folder_name,)
                    folder_item = QTreeWidgetItem([folder_name, "/".join(folder_prefix)])
                    parent_item.addChild(folder_item)
                    folder_items[folder_prefix] = folder_item
                    queue.append((folder_prefix, folder_item))

                # Add visible files
                for file_name, rel_path in visible_files:
                    item = QTreeWidgetItem([file_name, rel_path])
                    item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "file", "path": rel_path})
                    parent_item.addChild(item)

                # Append overflow indicator as a child of this specific folder node
                if total_children > folder_limit:
                    overflow_count = total_children - folder_limit
                    parent_item.addChild(QTreeWidgetItem([f"... {overflow_count} more", ""]))
        else:
            file_limit = 400
            for rel_path in matching_files[:file_limit]:
                item = QTreeWidgetItem([Path(rel_path).name, rel_path])
                item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "file", "path": rel_path})
                files_root.addChild(item)
            if len(matching_files) > file_limit:
                files_root.addChild(QTreeWidgetItem([f"... {len(matching_files) - file_limit} more", ""]))

        matching_symbols, total_symbols = self._controller.matching_symbols(filter_text)
        symbols_label = (
            f"Symbols ({len(matching_symbols)}/{total_symbols})"
            if filter_text
            else f"Symbols ({total_symbols})"
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

        matching_excel_rows, total_excel_rows = self._controller.matching_excel_rows(filter_text)
        excel_label = (
            f"Excel Rows ({len(matching_excel_rows)}/{total_excel_rows})"
            if filter_text
            else f"Excel Rows ({total_excel_rows})"
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

        matching_skipped_files, total_skipped_files = self._controller.matching_skipped_files(filter_text)
        skipped_label = (
            f"Skipped Files ({len(matching_skipped_files)}/{total_skipped_files})"
            if filter_text
            else f"Skipped Files ({total_skipped_files})"
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
            path_text = self._payload_path(payload)
            self._open_path(path_text)
            return

        if kind == "symbol":
            self._tabs.setCurrentWidget(self.search_view)
            self.search_view.set_query(query=str(payload.get("name", "")), scope="symbols", execute=True)
            return

        if kind == "excel":
            self._tabs.setCurrentWidget(self.excel_view)
            self.excel_view.set_filter(query=str(payload.get("query", "")), execute=True)

        if kind == "skipped":
            self.statusBar().showMessage(
                f"Skipped file: {payload.get('path', '')} ({payload.get('stage', '')}: {payload.get('reason', '')})"
            )

    def _on_library_context_menu(self, position: QPoint) -> None:
        """Show unified context menu with open/copy/note actions for selected library item."""
        item = self._library_tree.itemAt(position)
        if item is None:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return

        from app.views.context_menu_builder import ContextMenuBuilder, ItemContext, ContextMenuCallbacks

        path_text = self._payload_path(payload)
        kind = str(payload.get("kind", ""))
        name = str(payload.get("name", ""))
        line = int(payload.get("line", 1)) if str(payload.get("line", "")).isdigit() else 1

        ctx = ItemContext(
            path=path_text,
            line=line if kind == "symbol" else None,
            symbol=name if kind == "symbol" else "",
            source="Indexed Library",
            title=f"Note: {name or Path(path_text).name}:{line}",
        )

        callbacks = ContextMenuCallbacks(
            open_file=lambda p, l: self._open_path(p),
            open_external=lambda p: self._open_path_external(p),
            create_note=self.create_note_for,
            trace_symbol=lambda s: (self._tabs.setCurrentWidget(self.call_graph_view), self.call_graph_view.trace_symbol(s)),
        )

        ContextMenuBuilder.exec_menu(self, self._library_tree.viewport().mapToGlobal(position), ctx, callbacks)

    def _on_subview_create_note(
        self,
        target_file: str,
        line: int,
        symbol: str,
        source: str,
        title: str,
        snippet: str,
    ) -> None:
        """Route cross-component note creation signals to the active NotesView tab."""
        self.create_note_for(
            target_file=target_file,
            line=line,
            symbol=symbol,
            source=source,
            title=title,
            snippet=snippet,
        )

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
        return self._path_controller.reference_location(path_text=path_text, line_text=line_text)

    def _open_path(self, path_text: str) -> None:
        """Open a file path in the embedded MVC editor if it exists."""
        resolved = self._resolve_path(path_text)
        if resolved is None or not resolved.exists():
            return
        self._open_in_mvc_editor(resolved)

    def _open_path_external(self, path_text: str) -> None:
        """Open a file path in the desktop shell if it exists."""
        resolved = self._resolve_path(path_text)
        if resolved is None or not resolved.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))

    def _open_in_mvc_editor(self, path: Path, line_number: int | None = None) -> bool:
        """Open a file path in the embedded MVC editor and focus that tab."""
        opened = self.mvc_editor_tab.open_file(path, line_number=line_number)
        if opened:
            self._tabs.setCurrentWidget(self.mvc_editor_tab)
        return opened

    def _resolve_path(self, path_text: str) -> Path | None:
        """Resolve relative index path against configured project root."""
        return self._path_controller.resolve_path(path_text)

    def _open_settings(self) -> None:
        dialog = SettingsView(self.index_manager.config, self)
        if dialog.exec():
            self._on_project_root_changed(self.index_manager.config.project_root)
            self.integrations_view.sync_from_config()
            self._action_auto_refresh.setChecked(self._controller.restart_auto_refresh())
            self._refresh_index()

    def _populate_recent_projects_menu(self) -> None:
        if not hasattr(self, "_recent_menu"):
            return
        self._recent_menu.clear()
        recent = list(getattr(self.index_manager.config, "recent_projects", []))
        current = self.index_manager.config.project_root
        if current and current not in recent:
            recent.insert(0, current)
            self.index_manager.config.recent_projects = recent[:10]
            from app.config import save_config
            save_config(self.index_manager.config)

        if not recent:
            action = QAction("No Recent Projects", self)
            action.setEnabled(False)
            self._recent_menu.addAction(action)
            return

        for p in recent[:10]:
            p_name = Path(p).name or p
            act = QAction(f"{p_name} ({p})", self)
            act.triggered.connect(lambda checked, path=p: self._on_project_root_changed(path))
            self._recent_menu.addAction(act)

    def _on_project_root_changed(self, project_root: str) -> None:
        """Synchronize all root-dependent integrations to the active library root."""
        normalized, mcp_status = self._controller.synchronize_project_root(project_root, self.mcp_server_manager)
        self.mvc_editor_tab.set_workspace_root(normalized)
        if hasattr(self, "call_graph_view"):
            self.call_graph_view.set_index_manager(self.index_manager)
        if hasattr(self, "notes_view"):
            self.notes_view.set_project_root(normalized)

        # Update recent projects list
        recent = list(getattr(self.index_manager.config, "recent_projects", []))
        if normalized and normalized not in recent:
            recent.insert(0, normalized)
            self.index_manager.config.recent_projects = recent[:10]
            from app.config import save_config
            save_config(self.index_manager.config)
            self._populate_recent_projects_menu()

        if mcp_status:
            self.integrations_view.refresh_status(mcp_status)

    def create_note_for(
        self,
        target_file: str = "",
        line: int = 1,
        symbol: str = "",
        source: str = "Editor",
        title: str = "",
        snippet: str = "",
    ) -> None:
        """Create a new note populated with context and switch to Notes tab."""
        self.notes_view.create_note_from_context(
            target_file=target_file,
            line=line,
            symbol=symbol,
            source=source,
            title=title,
            snippet=snippet,
        )
        self._tabs.setCurrentWidget(self.notes_view)

    def _toggle_auto_refresh(self, enabled: bool) -> None:
        """Enable or disable interval-based auto-refresh worker."""
        self._action_auto_refresh.setChecked(self._controller.toggle_auto_refresh(enabled))
        self._update_refresh_indicator()

    def _update_refresh_indicator(self) -> None:
        """Refresh status-bar labels for worker state, progress bar, RAM stats, and last refresh time."""
        status = self._controller.refresh_status()
        refresh_count = int(status.get("refresh_count") or 0)
        worker_running = bool(status.get("worker_running"))
        refresh_in_progress = bool(status.get("refresh_in_progress"))
        refresh_running_seconds = status.get("refresh_running_seconds")
        interval = float(status.get("interval_seconds") or 0.0)
        last_refresh = status.get("last_refresh_at") or "--"
        skipped_count = int(status.get("skipped_count") or 0)
        last_refresh_error = str(status.get("last_refresh_error") or "")
        worker_text = "running" if worker_running else "stopped"

        # RAM Usage summary
        process_ram_text = str(status.get("process_ram_text") or "--")
        system_ram_text = str(status.get("system_ram_text") or "--")
        sys_load = status.get("system_ram_load_percent")
        sys_load_text = f" (Sys: {sys_load}%)" if sys_load else ""
        self._ram_label.setText(f"RAM: {process_ram_text}{sys_load_text}")
        self._ram_label.setToolTip(f"Process Working Set: {process_ram_text}\nSystem Physical RAM: {system_ram_text}")

        # Progress tracking & active stage
        progress_stage = status.get("progress_stage")
        progress_percent = status.get("progress_percent")
        progress_completed = status.get("progress_completed")
        progress_total = status.get("progress_total")

        if refresh_count != self._last_applied_refresh_count:
            self._rebuild_library_tree()
            self.mvc_editor_tab.update_completer_words()
            self._last_applied_refresh_count = refresh_count
            self.statusBar().showMessage(self._controller.refresh_summary_text())

        if refresh_in_progress:
            # Show elapsed time and active stage so long-running scans are visibly active
            elapsed = int(refresh_running_seconds) if refresh_running_seconds is not None else 0
            worker_text = f"{worker_text}, indexing ({elapsed}s)"

            self._progress_bar.show()
            if progress_percent is not None:
                self._progress_bar.setRange(0, 100)
                self._progress_bar.setValue(int(progress_percent))
                self._progress_bar.setFormat(f"{int(progress_percent)}%")
            else:
                self._progress_bar.setRange(0, 0)
                self._progress_bar.setFormat("Indexing...")

            stage_desc = str(progress_stage or "Indexing workspace")
            if progress_total is not None and progress_completed is not None and progress_total > 0:
                stage_desc = f"{stage_desc} ({progress_completed}/{progress_total})"
            self.statusBar().showMessage(f"Indexing ({elapsed}s): {stage_desc}...")
        else:
            self._progress_bar.hide()

        self._auto_refresh_label.setText(f"Auto-Refresh: {worker_text} ({interval:.1f}s)")
        self._skipped_label.setText(f"Skipped: {skipped_count}")
        self._last_refresh_label.setText(f"Last Refresh: {last_refresh}")
        if last_refresh_error and last_refresh_error != self._last_reported_refresh_error:
            self.statusBar().showMessage(f"Refresh failed: {last_refresh_error}")
        self._last_reported_refresh_error = last_refresh_error
        if hasattr(self, "_action_auto_refresh"):
            self._action_auto_refresh.setChecked(worker_running)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop background workers before window teardown."""
        self._status_timer.stop()
        self._controller.stop_worker()
        self.mcp_server_manager.stop()
        super().closeEvent(event)
