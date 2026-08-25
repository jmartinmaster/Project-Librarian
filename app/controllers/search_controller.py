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

"""Search workflow controller for the Search Browser view."""

from __future__ import annotations

import csv
from pathlib import Path

from app.controllers.path_controller import PathController
from app.indexer.index_manager import IndexManager
from app.models.editor_model import launch_editor
from app.search.search_engine import search_snapshot


class SearchController:
    """Execute query workflows against in-memory index state."""

    def __init__(self, index_manager: IndexManager) -> None:
        self._index_manager = index_manager
        self._path_controller = PathController(index_manager=index_manager)

    def run_search(
        self,
        query: str,
        scope: str,
        limit: int = 100,
        match_case: bool = False,
        use_regex: bool = False,
    ) -> list[dict[str, object]]:
        """Run search with current state and return ranked results."""
        return search_snapshot(
            file_corpus=self._index_manager.state.file_corpus,
            symbols=self._index_manager.state.symbols,
            excel_rows=self._index_manager.state.excel_rows,
            query=query,
            scope=scope,
            limit=limit,
            match_case=match_case,
            use_regex=use_regex,
        )

    def line_context(
        self,
        path: str,
        line_number: int | None,
        fallback: str,
        title: str,
        context: int = 3,
    ) -> str:
        """Build multi-line context preview from the in-memory file corpus."""
        source = self._index_manager.state.file_corpus.get(path, "")
        lines = source.splitlines()
        if not lines:
            return "\n".join([f"Path: {path}", f"Title: {title}", f"Preview: {fallback}"])

        resolved_line = max(1, line_number or 1)
        start = max(1, resolved_line - context)
        end = min(len(lines), resolved_line + context)

        rendered = [f"Path: {path}", f"Line: {resolved_line}", ""]
        for ln in range(start, end + 1):
            marker = ">" if ln == resolved_line else " "
            rendered.append(f"{marker} {ln:4d} | {lines[ln - 1]}")
        return "\n".join(rendered)

    @staticmethod
    def export_results_to_csv(results: list[dict[str, object]], file_path: str) -> None:
        """Export search results to a CSV file path."""
        with open(file_path, "w", newline="", encoding="utf-8") as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow(["Title", "File", "Path", "Line", "Type", "File Type", "Preview"])
            for item in results:
                file_name = str(item.get("file") or (Path(str(item.get("path", ""))).name if item.get("path") else ""))
                writer.writerow(
                    [
                        item.get("title", ""),
                        file_name,
                        item.get("path", ""),
                        item.get("line", ""),
                        item.get("type", ""),
                        item.get("file_type", ""),
                        item.get("preview", ""),
                    ]
                )

    def open_external_editor(self, path_text: str, line_number: int | None) -> bool:
        """Open a result path in configured external editor."""
        resolved = self._path_controller.resolve_path(path_text)
        if resolved is None or not resolved.exists():
            return False
        return launch_editor(Path(resolved), line_number, self._index_manager.config)
