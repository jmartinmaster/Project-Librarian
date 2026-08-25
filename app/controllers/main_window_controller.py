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

"""Main window orchestration controller."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.indexer.index_manager import IndexManager, ScanEstimate
from app.models.mcp_server_manager import MCPServerManager


class MainWindowViewController:
    """Controller for refresh, worker lifecycle, and status metadata."""

    def __init__(self, index_manager: IndexManager) -> None:
        self._index_manager = index_manager

    def estimate_workspace_scan(
        self,
        project_root: str,
        progress_callback: Callable[[ScanEstimate], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ScanEstimate:
        """Scan a candidate workspace folder and estimate its RAM footprint.

        When `progress_callback` is supplied it receives live, partial
        `ScanEstimate` updates while the scan is running so a caller can
        show an adjusting progress popup instead of appearing frozen.
        """
        return self._index_manager.estimate_scan(
            project_root,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    def request_refresh(self) -> bool:
        """Request one asynchronous index refresh."""
        return self._index_manager.request_refresh_async()

    def refresh_status(self) -> dict[str, object]:
        """Read current refresh status metadata for status bar display."""
        return self._index_manager.refresh_status()

    def toggle_auto_refresh(self, enabled: bool) -> bool:
        """Enable or disable refresh worker and return actual worker state."""
        if enabled:
            self._index_manager.start_refresh_worker(force_restart=True)
        else:
            self._index_manager.stop_refresh_worker()
        return self._index_manager.is_refresh_worker_running()

    def restart_auto_refresh(self) -> bool:
        """Restart refresh worker from current config and return worker state."""
        self._index_manager.start_refresh_worker(force_restart=True)
        return self._index_manager.is_refresh_worker_running()

    def stop_worker(self) -> None:
        """Stop background refresh worker."""
        self._index_manager.stop_refresh_worker()

    def matching_files(self, filter_text: str) -> tuple[list[str], int]:
        """Return filtered file paths and total file count."""
        state = self._index_manager.state
        sorted_files = sorted(state.file_corpus.keys())
        if not filter_text:
            return sorted_files, len(state.file_corpus)
        matching = [
            rel_path
            for rel_path in sorted_files
            if filter_text in rel_path.lower() or filter_text in Path(rel_path).name.lower()
        ]
        return matching, len(state.file_corpus)

    def matching_symbols(self, filter_text: str) -> tuple[list[dict[str, object]], int]:
        """Return filtered symbols and total symbol count."""
        state = self._index_manager.state
        if not filter_text:
            return state.symbols, len(state.symbols)
        matching = [
            symbol
            for symbol in state.symbols
            if filter_text in str(symbol.get("name", "")).lower()
            or filter_text in str(symbol.get("path", "")).lower()
            or filter_text in str(symbol.get("kind", "")).lower()
        ]
        return matching, len(state.symbols)

    def matching_excel_rows(self, filter_text: str) -> tuple[list[dict[str, object]], int]:
        """Return filtered excel rows and total excel row count."""
        state = self._index_manager.state
        if not filter_text:
            return state.excel_rows, len(state.excel_rows)
        matching = [
            row
            for row in state.excel_rows
            if filter_text in str(row.get("file", "")).lower()
            or filter_text in str(row.get("field", "")).lower()
            or filter_text in str(row.get("value", "")).lower()
        ]
        return matching, len(state.excel_rows)

    def matching_skipped_files(self, filter_text: str) -> tuple[list[dict[str, str]], int]:
        """Return filtered skipped files and total skipped file count."""
        state = self._index_manager.state
        all_skipped_files = state.skipped_files
        if not filter_text:
            return all_skipped_files, len(all_skipped_files)
        matching = [
            item
            for item in all_skipped_files
            if filter_text in str(item.get("path", "")).lower()
            or filter_text in str(item.get("reason", "")).lower()
            or filter_text in str(item.get("stage", "")).lower()
        ]
        return matching, len(all_skipped_files)

    def refresh_summary_text(self) -> str:
        """Return status-bar summary text for current indexed state."""
        state = self._index_manager.state
        return (
            "Refreshed: "
            f"files={len(state.file_corpus)} symbols={len(state.symbols)} "
            f"excel_rows={len(state.excel_rows)} skipped={len(state.skipped_files)}"
        )

    def synchronize_project_root(self, project_root: str, mcp_manager: MCPServerManager) -> tuple[str, str | None]:
        """Apply project root and restart MCP manager when required."""
        normalized = str(Path(project_root or Path.cwd()).resolve())
        self._index_manager.config.project_root = normalized
        if not mcp_manager.is_running():
            return normalized, None
        mcp_manager.stop()
        started, message = mcp_manager.start()
        if started:
            return normalized, "MCP restarted for updated root"
        return normalized, f"MCP restart failed: {message}"
