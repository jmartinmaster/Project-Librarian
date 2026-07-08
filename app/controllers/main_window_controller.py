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

from app.indexer.index_manager import IndexManager


class MainWindowController:
    """Controller for refresh, worker lifecycle, and status metadata."""

    def __init__(self, index_manager: IndexManager) -> None:
        self._index_manager = index_manager

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

