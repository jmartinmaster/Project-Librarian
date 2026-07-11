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

"""Controller for the workspace assistant module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.workspace_service import WorkspaceService

if TYPE_CHECKING:
    from app.indexer.index_manager import IndexManager


class WorkspaceController:
    """Orchestrates workspace documentation and git summary workflows."""

    def __init__(self, index_manager: IndexManager) -> None:
        self.service = WorkspaceService(index_manager=index_manager)

    def get_git_summary(self) -> str:
        """Fetch and format the git summary."""
        return self.service.format_git_summary()

    def generate_docs_draft(self, changed_only: bool) -> str:
        """Generate documentation draft text."""
        return self.service.generate_docs_draft(changed_only=changed_only)

    def generate_changelog_draft(self, version_text: str | None, changed_only: bool) -> str:
        """Generate changelog draft text."""
        return self.service.generate_changelog_draft(
            version_text=version_text,
            changed_only=changed_only,
        )

    def save_output(self, file_path: str, content: str) -> None:
        """Save text content to a specified file."""
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(content + "\n")
