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
"""Controller for the workspace assistant operations."""

from __future__ import annotations

from app.indexer.index_manager import IndexManager
from app.models.workspace_model import WorkspaceModel


class WorkspaceController:
    """Delegates workspace actions from the view to the WorkspaceModel."""

    def __init__(self, index_manager: IndexManager) -> None:
        self.service = WorkspaceModel(index_manager=index_manager)

    def format_git_summary(self) -> str:
        """Fetch the git summary for the workspace."""
        return self.service.format_git_summary()

    def generate_docs_draft(self, changed_only: bool) -> str:
        """Generate a documentation draft text based on workspace state."""
        return self.service.generate_docs_draft(changed_only=changed_only)

    def generate_changelog_draft(self, version_text: str | None, changed_only: bool) -> str:
        """Generate a changelog draft text."""
        return self.service.generate_changelog_draft(
            version_text=version_text,
            changed_only=changed_only,
        )

    def save_output_to_file(self, file_path: str, content: str) -> None:
        """Save the provided output text to a file.
        
        Args:
            file_path: The destination path on disk.
            content: The text content to write.
            
        Raises:
            OSError: If there's an error writing to the file.
        """
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(content + "\n")
