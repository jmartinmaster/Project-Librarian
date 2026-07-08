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

"""Settings workflow controller."""

from __future__ import annotations

from pathlib import Path

from app.config import AppConfig, save_config
from app.indexer.excel_indexer import discover_headers, list_excel_files


class SettingsController:
    """Controller seam for settings persistence and Excel header discovery."""

    @staticmethod
    def discover_excel_columns(folder_text: str) -> list[str]:
        """Discover unique Excel headers from a configured folder path."""
        folder_path = Path(folder_text.strip())
        if not folder_path.exists():
            return []

        seen: set[str] = set()
        skipped_files: list[dict[str, str]] = []
        headers: list[str] = []
        for file_path in list_excel_files(folder_path):
            try:
                file_headers = discover_headers(file_path, skipped_files=skipped_files)
            except Exception:
                file_headers = []
            for header in file_headers:
                if header in seen:
                    continue
                seen.add(header)
                headers.append(header)
        return headers

    @staticmethod
    def persist_config(config: AppConfig) -> None:
        """Persist configuration."""
        save_config(config)
