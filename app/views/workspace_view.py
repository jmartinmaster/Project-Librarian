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
"""Workspace assistant tab with button-driven status and draft actions."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.controllers.workspace_controller import WorkspaceController
from app.indexer.index_manager import IndexManager


class WorkspaceView(QWidget):
    """Expose high-value monolith features through modular UI actions."""

    def __init__(self, index_manager: IndexManager, controller: WorkspaceController | None = None) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._controller = controller or WorkspaceController(index_manager=index_manager)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        options_layout = QHBoxLayout()
        self.changed_only_checkbox = QCheckBox("Changed files only", self)
        self.changed_only_checkbox.setObjectName("workspaceChangedOnly")
        self.changed_only_checkbox.setChecked(True)
        options_layout.addWidget(self.changed_only_checkbox)

        options_layout.addWidget(QLabel("Version:", self))
        self.version_input = QLineEdit(self)
        self.version_input.setObjectName("workspaceVersionInput")
        self.version_input.setPlaceholderText("Unreleased")
        self.version_input.setMaximumWidth(120)
        options_layout.addWidget(self.version_input)
        options_layout.addStretch(1)

        buttons_layout = QHBoxLayout()
        self.git_summary_button = QPushButton("Show Git Summary", self)
        self.git_summary_button.setObjectName("workspaceGitSummaryButton")
        self.docs_draft_button = QPushButton("Generate Docs Draft", self)
        self.docs_draft_button.setObjectName("workspaceDocsDraftButton")
        self.changelog_button = QPushButton("Generate Changelog Draft", self)
        self.changelog_button.setObjectName("workspaceChangelogDraftButton")
        self.save_output_button = QPushButton("Save Output...", self)
        self.save_output_button.setObjectName("workspaceSaveOutputButton")
        self.save_output_button.setEnabled(False)

        buttons_layout.addWidget(self.git_summary_button)
        buttons_layout.addWidget(self.docs_draft_button)
        buttons_layout.addWidget(self.changelog_button)
        buttons_layout.addWidget(self.save_output_button)
        buttons_layout.addStretch(1)

        layout.addLayout(options_layout)
        layout.addLayout(buttons_layout)

        self.output = QPlainTextEdit(self)
        self.output.setObjectName("workspaceOutput")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Use a button above to generate a workspace report or draft.")
        layout.addWidget(self.output)

        self.git_summary_button.clicked.connect(self.show_git_summary)
        self.docs_draft_button.clicked.connect(self.generate_docs_draft)
        self.changelog_button.clicked.connect(self.generate_changelog_draft)
        self.save_output_button.clicked.connect(self.save_output)

    def _set_output(self, text: str) -> None:
        self.output.setPlainText(text)
        self.save_output_button.setEnabled(bool(text.strip()))

    def _current_changed_only(self) -> bool:
        return self.changed_only_checkbox.isChecked()

    def show_git_summary(self) -> None:
        """Render git summary output."""
        summary = self._controller.format_git_summary()
        self._set_output(summary)

    def generate_docs_draft(self) -> None:
        """Generate and display documentation draft text."""
        content = self._controller.generate_docs_draft(changed_only=self._current_changed_only())
        self._set_output(content)

    def generate_changelog_draft(self) -> None:
        """Generate and display changelog draft text."""
        version_text = self.version_input.text().strip() or None
        content = self._controller.generate_changelog_draft(
            version_text=version_text,
            changed_only=self._current_changed_only(),
        )
        self._set_output(content)

    def save_output(self) -> None:
        """Save current output text to a markdown file chosen by the user."""
        content = self.output.toPlainText().strip()
        if not content:
            QMessageBox.information(self, "No Output", "Generate output first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Workspace Output",
            "",
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            self._controller.save_output_to_file(file_path, content)
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", f"Unable to save output:\n{exc}")
