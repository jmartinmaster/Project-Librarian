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
"""Integrated MVC Sync editor tab."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QCompleter,
    QMessageBox,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.indexer.index_manager import IndexManager

from app.views.mvc_sync.controller import EditorController
from app.views.mvc_sync.model import DocumentModel
from app.views.mvc_sync.view import EditorView


class MVCEditorTab(QWidget):
    """Embedded MVC Sync Editor with file-open integration hooks."""
    create_note_requested = pyqtSignal(str, int, str, str, str, str)  # file, line, symbol, source, title, snippet

    def __init__(self, workspace_root: str = "", index_manager: IndexManager | None = None) -> None:
        super().__init__()
        self.workspace_root = workspace_root
        self._index_manager = index_manager
        self._current_file_path: Path | None = None

        self._model = DocumentModel(config=self._index_manager.config if self._index_manager else None)
        self._view = EditorView()
        self._controller = EditorController(self._model, self._view)

        self._build_ui()
        self._apply_native_integration_mode()
        self.set_workspace_root(workspace_root)

        self._view.file_selected.connect(self._remember_current_file)
        self._model.triad_changed.connect(self._sync_current_file_from_model)
        self._view.ai_request_triggered.connect(self.process_ai_request)
        self._view.create_note_requested.connect(self.create_note_requested.emit)

        # Compatibility aliases for existing callers/tests.
        self.editor_tabs = self._view.main_tabs
        self.model_editor = self._view.model_pane.editor
        self.view_editor = self._view.view_pane.editor
        self.controller_editor = self._view.controller_pane.editor
        self.file_editor = self._view.controller_pane.editor

        self.model_editor.diagnostic_hovered.connect(self._on_diagnostic_hovered)
        self.view_editor.diagnostic_hovered.connect(self._on_diagnostic_hovered)
        self.controller_editor.diagnostic_hovered.connect(self._on_diagnostic_hovered)

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
        current_row.addWidget(self.current_file_edit)
        layout.addLayout(current_row)

        buttons_row = QHBoxLayout()
        self.save_current_button = QPushButton("Save Current File", self)
        self.save_current_button.setObjectName("mvcSaveCurrentFileButton")
        self.open_external_button = QPushButton("Open Externally", self)
        self.open_external_button.setObjectName("mvcOpenExternalButton")
        self.ai_request_button = QPushButton("Process #AI-request", self)
        self.ai_request_button.setObjectName("mvcAIRequestButton")
        self.trigger_ai_button = QPushButton("Trigger Local AI", self)
        self.trigger_ai_button.setObjectName("mvcTriggerAIButton")

        # MicroPython Live Code hardware action buttons
        self.mcu_run_button = QPushButton("⚡ Run on MCU", self)
        self.mcu_run_button.setObjectName("mvcMCURunButton")
        self.mcu_run_button.setToolTip("Execute active file on connected microcontroller (requires Live Code enabled)")

        self.mcu_debug_button = QPushButton("🚀 Upload & Debug", self)
        self.mcu_debug_button.setObjectName("mvcMCUDebugButton")
        self.mcu_debug_button.setToolTip("Upload active file to device flash, soft reset, and watch startup (requires Live Code enabled)")

        buttons_row.addWidget(self.save_current_button)
        buttons_row.addWidget(self.open_external_button)
        buttons_row.addWidget(self.ai_request_button)
        buttons_row.addWidget(self.trigger_ai_button)
        buttons_row.addWidget(self.mcu_run_button)
        buttons_row.addWidget(self.mcu_debug_button)
        buttons_row.addStretch(1)

        # Editor Mode Selector (Single vs Triad)
        buttons_row.addWidget(QLabel("Mode:", self))
        self.mode_combo = QComboBox(self)
        self.mode_combo.setObjectName("mvcEditorModeCombo")
        self.mode_combo.addItems(["Single File", "Triad (MVC)"])
        self.mode_combo.setToolTip("Switch between Single File Editor mode and Triad (MVC 3-pane) mode")
        self.mode_combo.currentTextChanged.connect(self._on_mode_combo_changed)
        buttons_row.addWidget(self.mode_combo)

        # Language Awareness Selector
        buttons_row.addWidget(QLabel("Language:", self))
        self.language_combo = QComboBox(self)
        self.language_combo.setObjectName("mvcLanguageCombo")
        self.language_combo.addItems(["Auto-Detect", "MicroPython", "Python (Standard)", "C / C++"])
        self.language_combo.setToolTip("Active syntax and indexing language mode")
        self.language_combo.currentTextChanged.connect(self._on_language_combo_changed)
        buttons_row.addWidget(self.language_combo)

        layout.addLayout(buttons_row)

        self._view.setParent(self)
        layout.addWidget(self._view)

        self.status_label = QLabel("Ready", self)
        self.status_label.setObjectName("mvcEditorStatusLabel")
        layout.addWidget(self.status_label)

        self.save_current_button.clicked.connect(self.save_current_file)
        self.open_external_button.clicked.connect(self.open_current_externally)
        self.ai_request_button.clicked.connect(lambda: self.process_ai_request(None))
        self.trigger_ai_button.clicked.connect(self.trigger_local_ai)
        self.mcu_run_button.clicked.connect(self.run_current_on_mcu)
        self.mcu_debug_button.clicked.connect(self.debug_current_on_mcu)
        self._view.definition_requested.connect(self.jump_to_symbol_definition)

    def _on_mode_combo_changed(self, text: str) -> None:
        """Switch between Single File and Triad (MVC) editing modes."""
        is_single = (text == "Single File")
        self._controller.editor_mode = "single" if is_single else "triad"
        self._view.set_editor_mode("single" if is_single else "triad")
        if self._current_file_path and self._current_file_path.exists():
            if is_single:
                self._controller.open_single_file(str(self._current_file_path))
            else:
                self._controller.open_file(str(self._current_file_path))

    def _on_language_combo_changed(self, text: str) -> None:
        """Handle manual language override in editor tab."""
        if text == "MicroPython":
            self._view.set_language_mode("micropython")
        elif text == "C / C++":
            self._view.set_language_mode("cpp")
        elif text == "Python (Standard)":
            self._view.set_language_mode("python")
        else:
            self._detect_and_apply_language_mode(self.get_active_editor_text())

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

        is_single = (getattr(self, "mode_combo", None) is None or self.mode_combo.currentText() == "Single File")
        self._view.set_editor_mode("single" if is_single else "triad")

    def _check_and_apply_micropython_syntax(self, content: str = "") -> None:
        """Backward compatibility shim."""
        self._detect_and_apply_language_mode(content)

    def _detect_and_apply_language_mode(self, content: str = "") -> None:
        """Auto-detect language (C/C++, MicroPython, Python) and apply appropriate highlighter."""
        if hasattr(self, "language_combo") and self.language_combo.currentText() != "Auto-Detect":
            mode = self.language_combo.currentText()
            if mode == "C / C++":
                self._view.set_language_mode("cpp")
            elif mode == "MicroPython":
                self._view.set_language_mode("micropython")
            else:
                self._view.set_language_mode("python")
            return

        # 1. Check file extension
        if self._current_file_path:
            ext = self._current_file_path.suffix.lower()
            if ext in {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx", ".ino"}:
                self._view.set_language_mode("cpp")
                return

        # 2. Check for MicroPython imports
        is_mcu = False
        if self._index_manager and getattr(self._index_manager.config, "micropython_mode", False):
            is_mcu = True
        elif content:
            from app.models.micropython_model import is_micropython_module
            for line in content.splitlines()[:25]:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    tokens = stripped.replace("from", " ").replace("import", " ").replace(",", " ").split()
                    if any(is_micropython_module(t) for t in tokens):
                        is_mcu = True
                        break

        self._view.set_language_mode("micropython" if is_mcu else "python")

    def set_workspace_root(self, workspace_root: str) -> None:
        """Set workspace root used by the embedded explorer and triad resolver."""
        normalized = str(Path(workspace_root or ".").resolve())
        self.workspace_root = normalized
        self.workspace_edit.setText(normalized)
        self._model.workspace_path = normalized
        self._detect_and_apply_language_mode()

    def open_file(self, file_path: str | Path, line_number: int | None = None) -> bool:
        """Open a file and optionally jump to a target line."""
        resolved = Path(file_path).resolve()
        if not resolved.exists() or not resolved.is_file():
            self.status_label.setText(f"File not found: {resolved}")
            return False

        mode = "single" if getattr(self, "mode_combo", None) and self.mode_combo.currentText() == "Single File" else "triad"
        self._controller.open_file(str(resolved), mode=mode)
        self._current_file_path = resolved
        self.current_file_edit.setText(str(resolved))

        if line_number is not None and line_number > 0:
            self._jump_to_line_for_path(resolved, line_number)

        self._view.main_tabs.setCurrentWidget(self._view.editor_tab)
        self._detect_and_apply_language_mode(self.get_active_editor_text())
        self.status_label.setText(f"Opened: {resolved}")
        return True

    def jump_to_symbol_definition(self, symbol_name: str) -> bool:
        """Find symbol in index or current triad and jump to its definition."""
        if not symbol_name:
            return False

        # 1. Search in index manager symbols if available
        if self._index_manager and self._index_manager.state and self._index_manager.state.symbols:
            matching = [
                s for s in self._index_manager.state.symbols
                if s.get("name") == symbol_name or s.get("qualified_name") == symbol_name
            ]
            if matching:
                target = matching[0]
                target_path = Path(self.workspace_root) / target["path"]
                line = int(target.get("line") or 1)
                self.open_file(target_path, line_number=line)
                self.status_label.setText(f"Jumped to: {symbol_name} ({target['path']}:{line})")
                return True

        # 2. Search in current open triad files
        role_map = {
            "model": self._model.get_path("model"),
            "view": self._model.get_path("view"),
            "controller": self._model.get_path("controller"),
        }
        for role, r_path in role_map.items():
            outline = self._model._triad_outlines.get(role) or {}
            for c in outline.get("classes", []):
                if c["name"] == symbol_name:
                    pane = getattr(self._view, f"{role}_pane")
                    pane.jump_to_line(c["start_line"])
                    self.status_label.setText(f"Jumped to: {symbol_name} (Line {c['start_line']})")
                    return True
                for m in c.get("methods", []):
                    if m["name"] == symbol_name:
                        pane = getattr(self._view, f"{role}_pane")
                        pane.jump_to_line(m["start_line"])
                        self.status_label.setText(f"Jumped to: {symbol_name} (Line {m['start_line']})")
                        return True
            for f in outline.get("functions", []):
                if f["name"] == symbol_name:
                    pane = getattr(self._view, f"{role}_pane")
                    pane.jump_to_line(f["start_line"])
                    self.status_label.setText(f"Jumped to: {symbol_name} (Line {f['start_line']})")
                    return True

        self.status_label.setText(f"Definition not found for: '{symbol_name}'")
        return False

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
        """Save dirty files via controller."""
        if getattr(self, "mode_combo", None) and self.mode_combo.currentText() == "Single File":
            if self._current_file_path:
                try:
                    content = self.controller_editor.toPlainText()
                    with open(self._current_file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.status_label.setText(f"Saved: {self._current_file_path.name}")
                    return
                except Exception as e:
                    self.status_label.setText(f"Save error: {e}")
                    return
        self._controller.save_all_files()
        self.status_label.setText("Saved current context")

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

    def process_ai_request(self, role: str | None = None) -> None:
        """
        Extracts the #AI-request comment from the target pane/role,
        initiates the background thread calling local AI, and replaces
        the editor's content on success.
        """
        config = self._index_manager.config if self._index_manager else None
        if not config:
            from app.config import load_config
            config = load_config()
            
        url = getattr(config, "ai_url", "http://localhost:11434/api/generate")
        model = getattr(config, "ai_model", "qwen2.5-coder:14b")

        target_role = role
        if not target_role:
            active = self._get_active_editor()
            if active:
                target_role = active[0]
            else:
                for r in ['controller', 'view', 'model']:
                    pane = getattr(self._view, f"{r}_pane")
                    code = pane.editor.toPlainText()
                    if self._extract_ai_request(code) is not None:
                        target_role = r
                        break
        
        if not target_role:
            QMessageBox.warning(self, "No Active Editor", "Please place your cursor inside the editor you want to edit.")
            return

        pane = getattr(self._view, f"{target_role}_pane")
        code = pane.editor.toPlainText()
        instruction = self._extract_ai_request(code)
        
        if not instruction:
            QMessageBox.warning(
                self, 
                "No Request Found", 
                "Could not find any `#AI-request: <instruction>` comment in this file.\n\n"
                "Please add a comment like:\n"
                "#AI-request: Add a helper method to calculate sums"
            )
            return

        self.status_label.setText(f"Sending request to local AI ({model})...")
        self.ai_request_button.setEnabled(False)
        pane.ai_btn.setEnabled(False)

        from app.views.mvc_sync.worker import AIRequestWorker
        from PyQt6.QtCore import QThread
        
        self._ai_thread = QThread()
        self._ai_worker = AIRequestWorker(url, model, code, instruction)
        self._ai_worker.moveToThread(self._ai_thread)
        
        self._ai_thread.started.connect(self._ai_worker.run)
        
        self._ai_worker.success.connect(lambda updated_code: self._on_ai_success(target_role, updated_code))
        self._ai_worker.refused.connect(self._on_ai_refused)
        self._ai_worker.error.connect(self._on_ai_error)
        
        self._ai_worker.finished.connect(self._ai_thread.quit)
        self._ai_worker.finished.connect(self._ai_worker.deleteLater)
        self._ai_thread.finished.connect(self._ai_thread.deleteLater)
        self._ai_worker.finished.connect(lambda: self.ai_request_button.setEnabled(True))
        self._ai_worker.finished.connect(lambda: pane.ai_btn.setEnabled(True))
        
        self._ai_thread.start()

    def _get_active_editor(self) -> tuple[str, QWidget] | None:
        if self._view.model_pane.editor.hasFocus():
            return 'model', self._view.model_pane
        elif self._view.view_pane.editor.hasFocus():
            return 'view', self._view.view_pane
        elif self._view.controller_pane.editor.hasFocus():
            return 'controller', self._view.controller_pane
        return None

    def get_active_editor_text(self) -> str:
        """Return the text of the currently active/focused editor pane or primary editor."""
        active = self._get_active_editor()
        if active:
            return active[1].editor.toPlainText()
        return self._view.controller_pane.editor.toPlainText()

    def _extract_ai_request(self, code: str) -> str | None:
        for line in code.splitlines():
            trimmed = line.strip()
            if trimmed.startswith("#AI-request:") or trimmed.startswith("# AI-request:"):
                parts = trimmed.split(":", 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return None

    def _on_ai_success(self, role: str, updated_code: str) -> None:
        pane = getattr(self._view, f"{role}_pane")
        pane.editor.setPlainText(updated_code)
        self._model.set_content(role, updated_code, mark_dirty=True)
        self.status_label.setText("AI edit applied successfully.")

    def _on_ai_refused(self, reason: str) -> None:
        QMessageBox.information(self, "AI Declined Request", reason)
        self.status_label.setText("Local AI declined to perform this edit.")

    def _on_ai_error(self, error_msg: str) -> None:
        QMessageBox.warning(
            self, 
            "AI Request Failed", 
            f"An error occurred calling the local AI:\n\n{error_msg}\n\n"
            "Please verify that Ollama is running and your model is downloaded."
        )
        self.status_label.setText("AI request failed.")

    def trigger_local_ai(self) -> None:
        """Save triad files and trigger AI propagation across Model, View, and Controller."""
        self.status_label.setText("Saving files and triggering local AI...")
        self.save_current_file()
        
        self.trigger_ai_button.setEnabled(False)
        self.status_label.setText("AI propagation in progress (background thread)...")
        
        def handle_result(ok: bool, msg: str):
            self.trigger_ai_button.setEnabled(True)
            from PyQt6.QtWidgets import QMessageBox
            if ok:
                self.status_label.setText(msg)
                QMessageBox.information(self, "AI Code Generation", msg)
            else:
                self.status_label.setText(f"AI generation failed: {msg}")
                QMessageBox.warning(self, "AI Code Generation Failed", msg)
                
        self._controller.run_ai_generation(handle_result)

    def open_current_externally(self) -> None:
        """Open currently active file in external shell-associated application."""
        if not self._current_file_path:
            self.status_label.setText("No active file to open externally")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_file_path)))

    def _on_diagnostic_hovered(self, message: str, file_path: str) -> None:
        if message:
            self.status_label.setText(message)
        elif file_path:
            self.status_label.setText(f"Opened: {file_path}")

    def run_current_on_mcu(self) -> None:
        """Run active file on connected microcontroller if Live Code is enabled."""
        if not self._index_manager or not getattr(self._index_manager.config, "micropython_live_code", False):
            QMessageBox.warning(
                self,
                "Live Code Disabled",
                "Live Code execution is currently disabled to prevent accidental writes.\n\n"
                "Enable 'Live Code Execution (Safety Guard)' in the Integrations tab or Settings to run on hardware.",
            )
            return

        if not self._current_file_path:
            QMessageBox.information(self, "No File Selected", "Please open or save a file first before running on MCU.")
            return

        self.save_current_file()
        from app.controllers.micropython_controller import MicroPythonController
        from app.views.sudo_dialog import SudoAuthDialog
        controller = MicroPythonController(self._index_manager.config)
        port = getattr(self._index_manager.config, "micropython_port", "auto")
        self.status_label.setText(f"Running {self._current_file_path.name} on MCU ({port})...")
        ok, output = controller.run_file(self._current_file_path, port=port)

        if not ok and controller.is_permission_error(output):
            sudo_dlg = SudoAuthDialog(port=port, error_detail=output, parent=self)
            if sudo_dlg.exec() == SudoAuthDialog.DialogCode.Accepted:
                password = sudo_dlg.get_password()
                if sudo_dlg.should_fix_port_permissions():
                    fix_ok, fix_msg = controller.fix_port_permissions(port, password)
                    if fix_ok:
                        self.status_label.setText("Port permissions fixed. Retrying run...")
                        ok, output = controller.run_file(self._current_file_path, port=port)
                    else:
                        QMessageBox.warning(self, "Permission Fix Failed", fix_msg)
                        return
                else:
                    ok, output = controller.run_with_sudo(["run", str(self._current_file_path)], password, port=port)

        if ok:
            self.status_label.setText(f"MCU execution complete: {self._current_file_path.name}")
            QMessageBox.information(self, "MCU Run Output", f"Device Output:\n\n{output}")
        else:
            self.status_label.setText(f"MCU execution failed: {self._current_file_path.name}")
            QMessageBox.warning(self, "MCU Run Error", f"Failed to execute on device:\n\n{output}")

    def debug_current_on_mcu(self) -> None:
        """Upload active file, soft reset, and monitor startup sequence."""
        if not self._index_manager or not getattr(self._index_manager.config, "micropython_live_code", False):
            QMessageBox.warning(
                self,
                "Live Code Disabled",
                "Live Code execution is currently disabled to prevent accidental writes.\n\n"
                "Enable 'Live Code Execution (Safety Guard)' in the Integrations tab or Settings to upload and debug.",
            )
            return

        if not self._current_file_path:
            QMessageBox.information(self, "No File Selected", "Please open or save a file first before uploading.")
            return

        self.save_current_file()
        from app.controllers.micropython_controller import MicroPythonController
        from app.views.sudo_dialog import SudoAuthDialog
        controller = MicroPythonController(self._index_manager.config)
        port = getattr(self._index_manager.config, "micropython_port", "auto")
        self.status_label.setText(f"Uploading and debugging {self._current_file_path.name} on MCU...")
        
        ok, msg = controller.upload_file(self._current_file_path, remote_path=self._current_file_path.name, port=port)
        if not ok and controller.is_permission_error(msg):
            sudo_dlg = SudoAuthDialog(port=port, error_detail=msg, parent=self)
            if sudo_dlg.exec() == SudoAuthDialog.DialogCode.Accepted:
                password = sudo_dlg.get_password()
                if sudo_dlg.should_fix_port_permissions():
                    fix_ok, fix_msg = controller.fix_port_permissions(port, password)
                    if fix_ok:
                        self.status_label.setText("Permissions fixed. Retrying upload...")
                        ok, msg = controller.upload_file(self._current_file_path, remote_path=self._current_file_path.name, port=port)
                    else:
                        QMessageBox.warning(self, "Permission Fix Failed", fix_msg)
                        return
                else:
                    ok, msg = controller.run_with_sudo(["fs", "cp", str(self._current_file_path), f":{self._current_file_path.name}"], password, port=port)

        if ok:
            controller.soft_reset(port=port)
            self.status_label.setText(f"Uploaded & Reset: {self._current_file_path.name}. Monitor output in Integrations tab.")
            QMessageBox.information(
                self,
                "Upload & Debug Started",
                f"{msg}\n\nDevice was soft-reset. Open the 'Integrations' tab to monitor the live REPL startup sequence!",
            )
        else:
            self.status_label.setText("Upload & Debug failed.")
            QMessageBox.warning(self, "Upload Failed", f"Could not upload file to device:\n\n{msg}")
