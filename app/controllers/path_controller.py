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

"""Controller helpers for path/reference operations shared by views."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_manager import IndexManager
from app.models.path_model import absolute_containing_folder


class PathController:
    """Resolve relative index paths against configured project root."""

    def __init__(self, index_manager: IndexManager) -> None:
        self._index_manager = index_manager

    def resolve_path(self, path_text: str) -> Path | None:
        """Resolve a relative or absolute path text into a filesystem path."""
        if not path_text:
            return None
        candidate = Path(path_text)
        if candidate.is_absolute():
            return candidate
        repo_root = Path(self._index_manager.config.project_root or Path.cwd())
        return (repo_root / candidate).resolve()

    @staticmethod
    def reference_location(path_text: str, line_text: str) -> str:
        """Build path:line reference text suitable for clipboard operations."""
        if path_text and line_text:
            return f"{path_text}:{line_text}"
        return path_text

    def containing_folder_path(self, path_text: str) -> str:
        """Return absolute containing-folder path for clipboard actions."""
        return absolute_containing_folder(path_text, self._index_manager.config.project_root or Path.cwd())
