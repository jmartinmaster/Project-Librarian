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

"""Popup dialog showing live workspace scan progress before loading a project."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.controllers.main_window_controller import MainWindowViewController
from app.indexer.index_manager import ScanEstimate


class _WorkspaceScanWorker(QThread):
    """Runs a workspace scan estimate on a background thread and reports progress."""

    progress = pyqtSignal(object)  # ScanEstimate (partial)
    finished_scan = pyqtSignal(object)  # ScanEstimate (final)

    def __init__(self, controller: MainWindowViewController, project_root: str) -> None:
        super().__init__()
        self._controller = controller
        self._project_root = project_root
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Ask the running scan to stop as soon as possible."""
        self._cancel_requested = True

    def run(self) -> None:
        estimate = self._controller.estimate_workspace_scan(
            self._project_root,
            progress_callback=self.progress.emit,
            cancel_check=lambda: self._cancel_requested,
        )
        self.finished_scan.emit(estimate)


class WorkspaceScanProgressDialog(QDialog):
    """Modal popup that scans a workspace folder while showing a live RAM estimate.

    An indeterminate progress bar plus continuously updating file count,
    on-disk size, and estimated RAM labels keep the UI visibly active while
    scanning, instead of appearing frozen during large workspace scans.
    """

    def __init__(
        self,
        controller: MainWindowViewController,
        project_root: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scanning Workspace...")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._result_estimate: ScanEstimate | None = None
        self._cancelled = False

        layout = QVBoxLayout(self)

        self._status_label = QLabel(f"Scanning: {project_root}", self)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 0)  # Busy indicator: total file count is unknown up front.
        layout.addWidget(self._progress_bar)

        self._files_label = QLabel("Files scanned: 0", self)
        self._size_label = QLabel("On-disk size so far: 0 B", self)
        self._ram_label = QLabel("Estimated RAM required: 0 B", self)
        layout.addWidget(self._files_label)
        layout.addWidget(self._size_label)
        layout.addWidget(self._ram_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        button_box.rejected.connect(self._on_cancel_clicked)
        layout.addWidget(button_box)

        self._worker = _WorkspaceScanWorker(controller, project_root)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_scan.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)

    def exec(self) -> int:  # type: ignore[override]
        self._worker.start()
        return super().exec()

    def _on_progress(self, estimate: ScanEstimate) -> None:
        self._files_label.setText(f"Files scanned: {estimate.file_count}")
        self._size_label.setText(f"On-disk size so far: {estimate.total_size_text}")
        self._ram_label.setText(f"Estimated RAM required: {estimate.estimated_ram_text}")

    def _on_finished(self, estimate: ScanEstimate) -> None:
        self._result_estimate = estimate
        self._worker.wait()
        if estimate.cancelled:
            self.reject()
        else:
            self._on_progress(estimate)
            self.accept()

    def _on_cancel_clicked(self) -> None:
        self._cancelled = True
        self._status_label.setText("Cancelling scan...")
        self._worker.request_cancel()

    def result_estimate(self) -> ScanEstimate | None:
        """Return the final scan estimate, or None if cancelled before completion."""
        return self._result_estimate

    def was_cancelled(self) -> bool:
        """Return True when the user cancelled the scan before it finished."""
        return self._cancelled
