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

"""Integrated MVC Sync editor tab."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCompleter,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.indexer.index_manager import IndexManager

from app.views.mvc_sync.controller import EditorController
from app.views.mvc_sync.model import DocumentModel
from app.views.mvc_sync.view import EditorView


class MVCEditorTab(QWidget):
    """Embedded MVC Sync Editor with file-open integration hooks."""

    def __init__(self, workspace_root: str = "", index_manager: IndexManager | None = None) -> None:
        super().__init__()
        self.workspace_root = workspace_root
        self._index_manager = index_manager
        self._current_file_path: Path | None = None

        self._model = DocumentModel()
        self._view = EditorView()
        self._controller = EditorController(self._model, self._view)

        self._build_ui()
        self._apply_native_integration_mode()
        self.set_workspace_root(workspace_root)

        self._view.file_selected.connect(self._remember_current_file)
        self._model.triad_changed.connect(self._sync_current_file_from_model)

        # Compatibility aliases for existing callers/tests.
        self.editor_tabs = self._view.main_tabs
        self.model_editor = self._view.model_pane.editor
        self.view_editor = self._view.view_pane.editor
        self.controller_editor = self._view.controller_pane.editor
        self.file_editor = self._view.controller_pane.editor

        self.update_completer_words()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Workspace:", self))
        self.workspace_edit = QLineEdit(self)
        self.workspace_edit.setObjectName("mvcWorkspaceEdit")
        self.workspace_edit.setReadOnly(True)
        top_row.addWidget(self.workspace_edit)
        layout.addLayout(top_row)

        current_row = QHBoxLayout()
        current_row.addWidget(QLabel("Current File:", self))
        self.current_file_edit = QLineEdit(self)
        self.current_file_edit.setObjectName("mvcCurrentFileEdit")
        self.current_file_edit.setReadOnly(True)
        self.save_current_button = QPushButton("Save Current File", self)
        self.save_current_button.setObjectName("mvcSaveCurrentFileButton")
        self.open_external_button = QPushButton("Open Externally", self)
        self.open_external_button.setObjectName("mvcOpenExternalButton")
        current_row.addWidget(self.current_file_edit)
        current_row.addWidget(self.save_current_button)
        current_row.addWidget(self.open_external_button)
        layout.addLayout(current_row)

        self._view.setParent(self)
        layout.addWidget(self._view)

        self.status_label = QLabel("Ready", self)
        self.status_label.setObjectName("mvcEditorStatusLabel")
        layout.addWidget(self.status_label)

        self.save_current_button.clicked.connect(self.save_current_file)
        self.open_external_button.clicked.connect(self.open_current_externally)

    def _apply_native_integration_mode(self) -> None:
        """Strip standalone MVC shell UI and align with Librarian-hosted experience."""
        workspace_tab = getattr(self._view, "workspace_tab", None)
        if workspace_tab is not None:
            index = self._view.main_tabs.indexOf(workspace_tab)
            if index >= 0:
                self._view.main_tabs.removeTab(index)

        # Keep only the editor/inspector content surface inside Librarian.
        self._view.main_tabs.tabBar().setVisible(False)
        self._view.menuBar().setVisible(False)

        toolbar = getattr(self._view, "toolbar", None)
        if toolbar is not None:
            toolbar.setVisible(False)

        console_widget = getattr(self._view, "console_widget", None)
        if console_widget is not None:
            console_widget.setVisible(False)
            self._view.vertical_splitter.setSizes([1, 0])

        # Drop standalone catppuccin styling so the tab inherits Librarian theme.
        self._view.setStyleSheet("")
        for child in self._view.findChildren(QWidget):
            child.setStyleSheet("")

    def set_workspace_root(self, workspace_root: str) -> None:
        """Set workspace root used by the embedded explorer and triad resolver."""
        normalized = str(Path(workspace_root or ".").resolve())
        self.workspace_root = normalized
        self.workspace_edit.setText(normalized)
        self._model.workspace_path = normalized

    def open_file(self, file_path: str | Path, line_number: int | None = None) -> bool:
        """Open a file and optionally jump to a target line."""
        resolved = Path(file_path).resolve()
        if not resolved.exists() or not resolved.is_file():
            self.status_label.setText(f"File not found: {resolved}")
            return False

        self._controller.open_file(str(resolved))
        self._current_file_path = resolved
        self.current_file_edit.setText(str(resolved))

        if line_number is not None and line_number > 0:
            self._jump_to_line_for_path(resolved, line_number)

        self._view.main_tabs.setCurrentWidget(self._view.editor_tab)
        self.status_label.setText(f"Opened: {resolved}")
        return True

    def _jump_to_line_for_path(self, resolved: Path, line_number: int) -> None:
        role_map = {
            "model": self._model.get_path("model"),
            "view": self._model.get_path("view"),
            "controller": self._model.get_path("controller"),
        }
        for role, role_path in role_map.items():
            if role_path and Path(role_path).resolve() == resolved:
                pane = getattr(self._view, f"{role}_pane")
                pane.jump_to_line(line_number)
                return
        self._view.controller_pane.jump_to_line(line_number)

    def _remember_current_file(self, path_text: str) -> None:
        candidate = Path(path_text)
        if candidate.exists() and candidate.is_file():
            self._current_file_path = candidate.resolve()
            self.current_file_edit.setText(str(self._current_file_path))

    def _sync_current_file_from_model(self, _model_path: str, _view_path: str, controller_path: str) -> None:
        if controller_path:
            self._remember_current_file(controller_path)

    def save_current_file(self) -> None:
        """Save dirty MVC files via controller."""
        self._controller.save_all_files()
        self.status_label.setText("Saved current MVC context")

    def open_current_externally(self) -> None:
        """Open currently active file in external shell-associated application."""
        current = self._current_file_path
        if current is None or not current.exists():
            self.status_label.setText("No current file to open externally")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(current)))
        self.status_label.setText(f"Opened externally: {current}")

    def load_triad(self) -> None:
        """Compatibility shim for prior tests/callers."""
        current = self._current_file_path or Path(self.workspace_root) / "main.py"
        self.open_file(current)

    def save_triad(self) -> None:
        """Compatibility shim for prior tests/callers."""
        self._controller.save_all_files()

    def update_completer_words(self) -> None:
        """Update code auto-completers with all indexed symbols in the workspace."""
        keywords = [
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "class", "continue", "def", "del", "elif", "else",
            "except", "finally", "for", "from", "global", "if", "import",
            "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
            "return", "try", "while", "with", "yield", "self", "print", "super",
            "QWidget", "QMainWindow", "QVBoxLayout", "QHBoxLayout", "QPushButton",
            "QLabel", "QLineEdit", "QTextEdit", "QPlainTextEdit", "QComboBox",
            "QCheckBox", "QListWidget", "QListWidgetItem", "QTabWidget", "QTreeWidget",
            "QTreeWidgetItem", "QFileDialog", "QMessageBox", "QStatusBar", "QToolBar",
            "QAction", "pyqtSignal", "QObject", "Qt", "QIcon", "QPixmap", "QColor",
            "QFont", "QSize", "QRect", "QTimer"
        ]
        
        if self._index_manager is not None:
            for sym in self._index_manager.state.symbols:
                name = sym.get("name")
                if name:
                    keywords.append(name)
        
        unique_words = sorted(list(set(keywords)))
        
        from PyQt6.QtWidgets import QCompleter
        from PyQt6.QtCore import QStringListModel
        
        for editor in [self.model_editor, self.view_editor, self.controller_editor]:
            completer = QCompleter(unique_words, self)
            completer.setModel(QStringListModel(unique_words, completer))
            editor.setCompleter(completer)
