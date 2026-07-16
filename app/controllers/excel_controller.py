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
"""Excel workflow controller for the Excel Browser view."""

from __future__ import annotations

from app.indexer.index_manager import IndexManager


class ExcelController:
    """Filter and return Excel row records from in-memory state."""

    def __init__(self, index_manager: IndexManager) -> None:
        self._index_manager = index_manager

    def filter_rows(self, query: str) -> list[dict[str, object]]:
        """Return filtered Excel records matching a case-insensitive query."""
        needle = query.strip().lower()
        rows = self._index_manager.state.excel_rows
        if not needle:
            return rows
        return [
            item
            for item in rows
            if needle in " ".join([str(item.get("file", "")), str(item.get("field", "")), str(item.get("value", ""))]).lower()
        ]

