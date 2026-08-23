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
"""Interactive Project Notes & Planned Edits Tab."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QPlainTextEdit, QSpinBox, QGroupBox, QMessageBox, QFileDialog
)

from app.models.notes_manager import NotesManager


class NotesView(QWidget):
    """
    Dedicated Notes tab for recording planned codebase edits, refactor ideas,
    and contextual notes linked directly to source files, lines, and symbols.
    """
    jump_requested = pyqtSignal(str, int)  # relative_path, line_number

    def __init__(self, project_root: str | Path = "", parent=None):
        super().__init__(parent)
        self.project_root = Path(project_root or ".")
        self._current_note_filename: str | None = None
        self._notes_cache: list[dict[str, Any]] = []
        self.init_ui()
        self.refresh_notes()

    def set_project_root(self, root: str | Path) -> None:
        self.project_root = Path(root or ".")
        self.refresh_notes()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Banner
        header_row = QHBoxLayout()
        title_label = QLabel("📝 Project Notes & Planned Edits", self)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #0969da;")
        header_row.addWidget(title_label)

        sub_label = QLabel("Saved in The_Librarian/ (isolated from codebase search index)", self)
        sub_label.setStyleSheet("color: #57606a; font-size: 11px;")
        header_row.addWidget(sub_label)
        header_row.addStretch(1)

        layout.addLayout(header_row)

        # Main Splitter: Notes List (Left) vs Note Editor (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left Column: List & Actions
        left_widget = QWidget(splitter)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Search / Filter Box
        self.search_input = QLineEdit(left_widget)
        self.search_input.setObjectName("notesSearchInput")
        self.search_input.setPlaceholderText("Filter notes by title, tag, or file...")
        self.search_input.textChanged.connect(self._filter_notes)
        left_layout.addWidget(self.search_input)

        self.notes_list = QListWidget(left_widget)
        self.notes_list.setObjectName("notesList")
        self.notes_list.itemSelectionChanged.connect(self._on_note_selected)
        left_layout.addWidget(self.notes_list, stretch=1)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("+ New Note", left_widget)
        self.btn_new.setObjectName("notesNewButton")
        self.btn_new.setStyleSheet("background-color: #2da44e; color: #ffffff; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        self.btn_new.clicked.connect(self.new_note)

        self.btn_delete = QPushButton("Delete", left_widget)
        self.btn_delete.setObjectName("notesDeleteButton")
        self.btn_delete.setStyleSheet("background-color: #cf222e; color: #ffffff; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        self.btn_delete.clicked.connect(self.delete_current_note)

        self.btn_refresh = QPushButton("↺ Refresh", left_widget)
        self.btn_refresh.clicked.connect(self.refresh_notes)

        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_refresh)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_widget)

        # Right Column: Note Detail & Editor
        right_widget = QWidget(splitter)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)

        # Title Row
        title_row = QHBoxLayout()
        title_lbl = QLabel("Title:", right_widget)
        title_lbl.setStyleSheet("font-weight: bold;")
        self.title_edit = QLineEdit(right_widget)
        self.title_edit.setObjectName("noteTitleEdit")
        self.title_edit.setPlaceholderText("Brief title or summary of planned change...")
        title_row.addWidget(title_lbl)
        title_row.addWidget(self.title_edit, 1)

        self.source_label = QLabel("Manual", right_widget)
        self.source_label.setStyleSheet("background: #ddf4ff; color: #0969da; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 2px 6px;")
        title_row.addWidget(self.source_label)

        right_layout.addLayout(title_row)

        # Target Reference Card
        ref_group = QGroupBox("Target Codebase Reference", right_widget)
        ref_layout = QHBoxLayout(ref_group)
        ref_layout.setContentsMargins(8, 6, 8, 6)
        ref_layout.setSpacing(8)

        ref_layout.addWidget(QLabel("File:"))
        self.target_file_edit = QLineEdit(ref_group)
        self.target_file_edit.setObjectName("noteTargetFileEdit")
        self.target_file_edit.setPlaceholderText("e.g. app/models/runner.py")
        ref_layout.addWidget(self.target_file_edit, 2)

        self.btn_browse_file = QPushButton("📁", ref_group)
        self.btn_browse_file.setToolTip("Browse file")
        self.btn_browse_file.clicked.connect(self._browse_target_file)
        ref_layout.addWidget(self.btn_browse_file)

        ref_layout.addWidget(QLabel("Line:"))
        self.target_line_spin = QSpinBox(ref_group)
        self.target_line_spin.setObjectName("noteTargetLineSpin")
        self.target_line_spin.setRange(1, 999999)
        self.target_line_spin.setValue(1)
        ref_layout.addWidget(self.target_line_spin)

        ref_layout.addWidget(QLabel("Symbol:"))
        self.target_symbol_edit = QLineEdit(ref_group)
        self.target_symbol_edit.setObjectName("noteTargetSymbolEdit")
        self.target_symbol_edit.setPlaceholderText("e.g. run_audit")
        ref_layout.addWidget(self.target_symbol_edit, 1)

        self.btn_jump = QPushButton("Jump to in Editor ➔", ref_group)
        self.btn_jump.setObjectName("noteJumpButton")
        self.btn_jump.setStyleSheet("background-color: #0969da; color: #ffffff; font-weight: bold; padding: 3px 8px; border-radius: 4px;")
        self.btn_jump.clicked.connect(self._jump_to_target)
        ref_layout.addWidget(self.btn_jump)

        right_layout.addWidget(ref_group)

        # Tags Row
        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel("Tags / Categories:"))
        self.tags_edit = QLineEdit(right_widget)
        self.tags_edit.setObjectName("noteTagsEdit")
        self.tags_edit.setPlaceholderText("e.g. refactor, bug, micropython, ui")
        tags_row.addWidget(self.tags_edit, 1)
        right_layout.addLayout(tags_row)

        # Note Description / Content
        right_layout.addWidget(QLabel("Planned Changes & Description:", right_widget))
        self.note_content_edit = QPlainTextEdit(right_widget)
        self.note_content_edit.setObjectName("noteContentEdit")
        self.note_content_edit.setPlaceholderText("Detailed notes on what to edit, reasons, edge cases, and steps...")
        self.note_content_edit.setStyleSheet("font-size: 12px; line-height: 1.4;")
        right_layout.addWidget(self.note_content_edit, 2)

        # Code Snippet / Draft Diff
        right_layout.addWidget(QLabel("Code Snippet / Draft Diff (Optional):", right_widget))
        self.code_snippet_edit = QPlainTextEdit(right_widget)
        self.code_snippet_edit.setObjectName("noteSnippetEdit")
        self.code_snippet_edit.setPlaceholderText("Optional code draft, snippet, or diff...")
        mono_font = QFont("Consolas", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_snippet_edit.setFont(mono_font)
        self.code_snippet_edit.setStyleSheet("background-color: #11111b; color: #a6e3a1; border-radius: 4px; padding: 4px;")
        right_layout.addWidget(self.code_snippet_edit, 1)

        # Bottom Row: Save & Status
        bottom_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 Save Note", right_widget)
        self.btn_save.setObjectName("noteSaveButton")
        self.btn_save.setStyleSheet("background-color: #0969da; color: #ffffff; font-weight: bold; font-size: 12px; padding: 6px 16px; border-radius: 4px;")
        self.btn_save.clicked.connect(self.save_current_note)
        bottom_row.addWidget(self.btn_save)

        self.status_label = QLabel("Ready", right_widget)
        self.status_label.setStyleSheet("color: #57606a; font-size: 11px;")
        bottom_row.addWidget(self.status_label, 1)

        right_layout.addLayout(bottom_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([320, 750])

        layout.addWidget(splitter, 1)

    def refresh_notes(self) -> None:
        """Load and display all notes from The_Librarian/."""
        self._notes_cache = NotesManager.list_notes(self.project_root)
        self._render_notes_list(self._notes_cache)

    def _render_notes_list(self, notes: list[dict[str, Any]]) -> None:
        self.notes_list.clear()
        for note in notes:
            title = note.get("title") or "Untitled Note"
            target_f = note.get("target_file", "")
            target_l = note.get("target_line", 1)
            filename = note.get("_filename", "")
            tags = ", ".join(note.get("tags", [])) if isinstance(note.get("tags"), list) else str(note.get("tags", ""))

            line1 = f"📌 {title}"
            line2 = f"   {target_f}:{target_l}" if target_f else f"   {filename}"
            if tags:
                line2 += f"  [{tags}]"

            item = QListWidgetItem(f"{line1}\n{line2}")
            item.setData(Qt.ItemDataRole.UserRole, note)
            self.notes_list.addItem(item)

        self.status_label.setText(f"Indexed {len(notes)} note(s) in The_Librarian/")

    def _filter_notes(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._render_notes_list(self._notes_cache)
            return

        filtered = []
        for n in self._notes_cache:
            title = str(n.get("title", "")).lower()
            content = str(n.get("note_content", "")).lower()
            tf = str(n.get("target_file", "")).lower()
            tags = str(n.get("tags", "")).lower()
            if q in title or q in content or q in tf or q in tags:
                filtered.append(n)
        self._render_notes_list(filtered)

    def _on_note_selected(self) -> None:
        items = self.notes_list.selectedItems()
        if not items:
            return
        note = items[0].data(Qt.ItemDataRole.UserRole)
        if not note:
            return

        self._current_note_filename = note.get("_filename")
        self.title_edit.setText(note.get("title", ""))
        self.target_file_edit.setText(note.get("target_file", ""))
        self.target_line_spin.setValue(int(note.get("target_line") or 1))
        self.target_symbol_edit.setText(note.get("target_symbol", ""))
        self.source_label.setText(note.get("source_component", "Manual"))

        tags_val = note.get("tags", [])
        if isinstance(tags_val, list):
            self.tags_edit.setText(", ".join(tags_val))
        else:
            self.tags_edit.setText(str(tags_val))

        self.note_content_edit.setPlainText(note.get("note_content", ""))
        self.code_snippet_edit.setPlainText(note.get("code_snippet", ""))
        self.status_label.setText(f"Loaded: {self._current_note_filename}")

    def new_note(self) -> None:
        """Clear editor fields for creating a new note."""
        self._current_note_filename = None
        self.notes_list.clearSelection()
        self.title_edit.clear()
        self.target_file_edit.clear()
        self.target_line_spin.setValue(1)
        self.target_symbol_edit.clear()
        self.source_label.setText("Manual")
        self.tags_edit.clear()
        self.note_content_edit.clear()
        self.code_snippet_edit.clear()
        self.title_edit.setFocus()
        self.status_label.setText("New note scratchpad ready.")

    def create_note_from_context(
        self,
        target_file: str = "",
        line: int = 1,
        symbol: str = "",
        source: str = "Editor",
        title: str = "",
        snippet: str = "",
        content: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """Populate fields from external component context and focus."""
        self.new_note()
        self.target_file_edit.setText(target_file)
        self.target_line_spin.setValue(max(1, line))
        self.target_symbol_edit.setText(symbol)
        self.source_label.setText(source)
        if title:
            self.title_edit.setText(title)
        else:
            ref_name = Path(target_file).name if target_file else symbol
            self.title_edit.setText(f"Edit {ref_name}:{line}")

        if snippet:
            self.code_snippet_edit.setPlainText(snippet)
        if content:
            self.note_content_edit.setPlainText(content)
        if tags:
            self.tags_edit.setText(", ".join(tags))

        self.note_content_edit.setFocus()
        self.status_label.setText(f"Note prepared from {source}.")

    def save_current_note(self) -> bool:
        """Save active note to The_Librarian/."""
        title = self.title_edit.text().strip()
        if not title:
            title = "Untitled Note"
            self.title_edit.setText(title)

        tags_raw = self.tags_edit.text().split(",")
        tags = [t.strip() for t in tags_raw if t.strip()]

        payload = {
            "title": title,
            "target_file": self.target_file_edit.text().strip(),
            "target_line": self.target_line_spin.value(),
            "target_symbol": self.target_symbol_edit.text().strip(),
            "source_component": self.source_label.text(),
            "tags": tags,
            "note_content": self.note_content_edit.toPlainText(),
            "code_snippet": self.code_snippet_edit.toPlainText(),
        }

        ok, msg, filename = NotesManager.save_note(
            repo_root=self.project_root,
            note_data=payload,
            filename=self._current_note_filename,
        )

        if ok:
            self._current_note_filename = filename
            self.status_label.setText(msg)
            self.refresh_notes()
            return True
        else:
            QMessageBox.warning(self, "Save Error", msg)
            self.status_label.setText(msg)
            return False

    def delete_current_note(self) -> None:
        """Delete currently open note from disk."""
        if not self._current_note_filename:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete note '{self._current_note_filename}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        ok, msg = NotesManager.delete_note(self.project_root, self._current_note_filename)
        if ok:
            self.new_note()
            self.refresh_notes()
        else:
            QMessageBox.warning(self, "Delete Error", msg)

    def _browse_target_file(self) -> None:
        initial = str(self.project_root)
        f_path, _ = QFileDialog.getOpenFileName(self, "Select Target File", initial, "All Files (*)")
        if f_path:
            try:
                rel = Path(f_path).relative_to(self.project_root).as_posix()
                self.target_file_edit.setText(rel)
            except Exception:
                self.target_file_edit.setText(f_path)

    def _jump_to_target(self) -> None:
        f_path = self.target_file_edit.text().strip()
        if not f_path:
            QMessageBox.information(self, "No Target File", "Please specify a target file path.")
            return
        line = self.target_line_spin.value()
        self.jump_requested.emit(f_path, line)
