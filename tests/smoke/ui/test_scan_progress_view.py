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

"""Smoke tests for the live workspace scan progress popup."""

from __future__ import annotations

from pathlib import Path

from app.controllers.main_window_controller import MainWindowViewController
from app.indexer.index_manager import IndexManager
from app.views.scan_progress_view import WorkspaceScanProgressDialog


def test_scan_progress_dialog_completes_and_reports_final_estimate(qtbot, app_config, sample_repo: Path):
    manager = IndexManager(app_config)
    controller = MainWindowViewController(manager)
    dialog = WorkspaceScanProgressDialog(controller, str(sample_repo))
    qtbot.addWidget(dialog)

    dialog.exec()

    assert dialog.was_cancelled() is False
    estimate = dialog.result_estimate()
    assert estimate is not None
    assert estimate.file_count == 2
    assert "Files scanned: 2" in dialog._files_label.text()
    assert "Estimated RAM required" in dialog._ram_label.text()


def test_scan_progress_dialog_cancel_stops_scan_and_reports_cancelled(qtbot, app_config, sample_repo: Path):
    manager = IndexManager(app_config)
    controller = MainWindowViewController(manager)
    dialog = WorkspaceScanProgressDialog(controller, str(sample_repo))
    qtbot.addWidget(dialog)

    # Request cancel before the worker starts so the scan stops on its very
    # first cancel_check() without racing against a real event loop tick.
    dialog._on_cancel_clicked()
    dialog.exec()

    assert dialog.was_cancelled() is True
