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

from app.indexer.index_manager import IndexManager
from app.services.workspace_service import WorkspaceService


class WorkspaceBrowser(QWidget):
    """Expose high-value monolith features through modular UI actions."""

    def __init__(self, index_manager: IndexManager) -> None:
        super().__init__()
        self.index_manager = index_manager
        self.service = WorkspaceService(index_manager=index_manager)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()

        self.changed_only_checkbox = QCheckBox("Changed files only", self)
        self.changed_only_checkbox.setObjectName("workspaceChangedOnly")
        self.changed_only_checkbox.setChecked(True)
        controls.addWidget(self.changed_only_checkbox)

        controls.addWidget(QLabel("Version:", self))
        self.version_input = QLineEdit(self)
        self.version_input.setObjectName("workspaceVersionInput")
        self.version_input.setPlaceholderText("Unreleased")
        controls.addWidget(self.version_input)

        self.git_summary_button = QPushButton("Show Git Summary", self)
        self.git_summary_button.setObjectName("workspaceGitSummaryButton")
        self.docs_draft_button = QPushButton("Generate Docs Draft", self)
        self.docs_draft_button.setObjectName("workspaceDocsDraftButton")
        self.changelog_button = QPushButton("Generate Changelog Draft", self)
        self.changelog_button.setObjectName("workspaceChangelogDraftButton")
        self.save_output_button = QPushButton("Save Output...", self)
        self.save_output_button.setObjectName("workspaceSaveOutputButton")
        self.save_output_button.setEnabled(False)

        controls.addWidget(self.git_summary_button)
        controls.addWidget(self.docs_draft_button)
        controls.addWidget(self.changelog_button)
        controls.addWidget(self.save_output_button)
        controls.addStretch(1)

        layout.addLayout(controls)

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
        summary = self.service.format_git_summary()
        self._set_output(summary)

    def generate_docs_draft(self) -> None:
        """Generate and display documentation draft text."""
        content = self.service.generate_docs_draft(changed_only=self._current_changed_only())
        self._set_output(content)

    def generate_changelog_draft(self) -> None:
        """Generate and display changelog draft text."""
        version_text = self.version_input.text().strip() or None
        content = self.service.generate_changelog_draft(
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
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(content + "\n")
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", f"Unable to save output:\n{exc}")
