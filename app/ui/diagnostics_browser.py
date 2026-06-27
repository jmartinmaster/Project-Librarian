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

"""Diagnostics and memory profiling manager widget."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.indexer.index_manager import IndexManager
from app.services.diagnostics_service import DiagnosticsService


class DiagnosticsBrowser(QWidget):
    """Widget providing memory tracing controls and PyQt6 leak detection."""

    def __init__(self, index_manager: IndexManager) -> None:
        super().__init__()
        self.index_manager = index_manager
        
        self.status_label: QLabel
        self.start_tracing_btn: QPushButton
        self.stop_tracing_btn: QPushButton
        self.snapshot_name: QLineEdit
        self.take_snapshot_btn: QPushButton
        self.old_snap_combo: QComboBox
        self.new_snap_combo: QComboBox
        self.compare_btn: QPushButton
        self.cycles_spin_box: QSpinBox
        self.run_leak_test_btn: QPushButton
        self.log_output: QPlainTextEdit

        self.service: LibrarianService | None = None
        self._load_ui()
        self._build_ui()
        self._init_service()
        self._update_ui_state()

    def _load_ui(self) -> None:
        """Load and bind the diagnostics Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "diagnostics_browser.ui"
        uic.loadUi(ui_path, self)

        status_label = self.findChild(QLabel, "statusLabel")
        start_tracing_btn = self.findChild(QPushButton, "startTracingBtn")
        stop_tracing_btn = self.findChild(QPushButton, "stopTracingBtn")
        snapshot_name = self.findChild(QLineEdit, "snapshotName")
        take_snapshot_btn = self.findChild(QPushButton, "takeSnapshotBtn")
        old_snap_combo = self.findChild(QComboBox, "oldSnapCombo")
        new_snap_combo = self.findChild(QComboBox, "newSnapCombo")
        compare_btn = self.findChild(QPushButton, "compareBtn")
        cycles_spin_box = self.findChild(QSpinBox, "cyclesSpinBox")
        run_leak_test_btn = self.findChild(QPushButton, "runLeakTestBtn")
        log_output = self.findChild(QPlainTextEdit, "logOutput")

        if any(
            w is None
            for w in [
                status_label,
                start_tracing_btn,
                stop_tracing_btn,
                snapshot_name,
                take_snapshot_btn,
                old_snap_combo,
                new_snap_combo,
                compare_btn,
                cycles_spin_box,
                run_leak_test_btn,
                log_output,
            ]
        ):
            raise RuntimeError("Diagnostics browser UI is missing required widgets.")

        self.status_label = status_label
        self.start_tracing_btn = start_tracing_btn
        self.stop_tracing_btn = stop_tracing_btn
        self.snapshot_name = snapshot_name
        self.take_snapshot_btn = take_snapshot_btn
        self.old_snap_combo = old_snap_combo
        self.new_snap_combo = new_snap_combo
        self.compare_btn = compare_btn
        self.cycles_spin_box = cycles_spin_box
        self.run_leak_test_btn = run_leak_test_btn
        self.log_output = log_output

    def _build_ui(self) -> None:
        self.log_output.setReadOnly(True)
        # Apply monospaced font style for neat tracing output lists
        font = self.log_output.font()
        font.setFamily("Courier New" if font.family() != "Courier New" else "Monospace")
        font.setPointSize(9)
        self.log_output.setFont(font)

        self.start_tracing_btn.clicked.connect(self.start_tracing)
        self.stop_tracing_btn.clicked.connect(self.stop_tracing)
        self.take_snapshot_btn.clicked.connect(self.take_snapshot)
        self.compare_btn.clicked.connect(self.compare_snapshots)
        self.run_leak_test_btn.clicked.connect(self.run_leak_test)

    def _init_service(self) -> None:
        try:
            self.service = DiagnosticsService()
        except Exception as exc:
            self.service = None
            self.log_output.setPlainText(
                f"Failed to initialize Diagnostics Service:\n{exc}\n\n"
                "Diagnostics, memory profiling, and leak testing are unavailable."
            )

    def _update_ui_state(self) -> None:
        if not self.service:
            self.status_label.setText("Status: Service Unavailable")
            self.start_tracing_btn.setEnabled(False)
            self.stop_tracing_btn.setEnabled(False)
            self.take_snapshot_btn.setEnabled(False)
            self.old_snap_combo.setEnabled(False)
            self.new_snap_combo.setEnabled(False)
            self.compare_btn.setEnabled(False)
            self.run_leak_test_btn.setEnabled(False)
            return
        
        status = self.service.profile_memory_payload("status")
        active = status.get("active", False)
        
        self.status_label.setText("Status: Tracing Active" if active else "Status: Tracing Inactive")
        self.start_tracing_btn.setEnabled(not active)
        self.stop_tracing_btn.setEnabled(active)
        self.take_snapshot_btn.setEnabled(True)
        
        saved = status.get("saved_snapshots", [])
        
        # Keep selection if possible
        old_val = self.old_snap_combo.currentText()
        new_val = self.new_snap_combo.currentText()
        
        self.old_snap_combo.clear()
        self.new_snap_combo.clear()
        
        self.old_snap_combo.addItems(saved)
        self.new_snap_combo.addItems(saved)
        
        if old_val in saved:
            self.old_snap_combo.setCurrentText(old_val)
        if new_val in saved:
            self.new_snap_combo.setCurrentText(new_val)

        self.compare_btn.setEnabled(len(saved) >= 2)

    def start_tracing(self) -> None:
        """Start memory tracing."""
        if not self.service:
            return
        res = self.service.profile_memory_payload("start", n_frames=25)
        self.log_output.setPlainText(res.get("message", "Started tracing."))
        self._update_ui_state()

    def stop_tracing(self) -> None:
        """Stop memory tracing and clear snapshots."""
        if not self.service:
            return
        res = self.service.profile_memory_payload("stop")
        self.log_output.setPlainText(res.get("message", "Stopped tracing."))
        self._update_ui_state()

    def take_snapshot(self) -> None:
        """Record current memory allocation snapshot state."""
        if not self.service:
            return
        name = self.snapshot_name.text().strip() or None
        self.snapshot_name.clear()
        
        res = self.service.profile_memory_payload("take_snapshot", snapshot_name=name)
        if not res.get("ok"):
            self.log_output.setPlainText(res.get("error", "Failed to take snapshot."))
            return
            
        output = [
            f"Snapshot recorded: {res.get('snapshot_name')}",
            f"Total Allocated Memory: {res.get('total_allocated_kb')} KB",
            "",
            "Top allocations:",
            f"{'Size (KB)':>10} | {'Count':>6} | Traceback Location",
            "-" * 60,
        ]
        for alloc in res.get("top_allocations", []):
            output.append(f"{alloc['size_kb']:10.2f} | {alloc['count']:6d} | {alloc['traceback']}")
            
        self.log_output.setPlainText("\n".join(output))
        self._update_ui_state()

    def compare_snapshots(self) -> None:
        """Calculate and render allocation comparison diff report."""
        if not self.service:
            return
        old_name = self.old_snap_combo.currentText()
        new_name = self.new_snap_combo.currentText()
        
        if not old_name or not new_name:
            QMessageBox.warning(self, "Selection Required", "Please select two snapshots to compare.")
            return

        res = self.service.profile_memory_payload("compare", snapshot_name=old_name, other_snapshot_name=new_name)
        if not res.get("ok", True):
            self.log_output.setPlainText(res.get("error", "Comparison failed."))
            return

        output = [
            res.get("comparison", "Comparison results:"),
            "",
            f"{'Diff (KB)':>10} | {'Size (KB)':>10} | {'Count Diff':>10} | Location",
            "-" * 70,
        ]
        for diff in res.get("top_differences", []):
            output.append(
                f"{diff['size_diff_kb']:10.2f} | {diff['size_kb']:10.2f} | {diff['count_diff']:10d} | {diff['traceback']}"
            )
            
        self.log_output.setPlainText("\n".join(output))

    def run_leak_test(self) -> None:
        """Run loop cycles of widget navigation and check for leaks."""
        if not self.service:
            return
        cycles = self.cycles_spin_box.value()
        
        self.log_output.setPlainText(f"Running navigation leak test with {cycles} cycles...\n(Please wait, this will cycle tabs in UI thread)")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Let UI render our status message first
            QApplication.processEvents()
            
            res = self.service.test_navigation_leaks_payload(cycles=cycles)
            if "error" in res:
                self.log_output.setPlainText(f"Leak test failed: {res['error']}")
                return

            output = [
                "Navigation Leak Test Completed.",
                f"Cycles run: {res.get('cycles_run')}",
                f"Net memory growth: {res.get('size_growth_kb')} KB",
                f"Allocated Before: {res.get('total_allocated_before_kb')} KB",
                f"Allocated After: {res.get('total_allocated_after_kb')} KB",
                "",
                "Growth details by location (Top Diff > 0):",
                f"{'Growth (KB)':>12} | {'Total Size':>12} | {'Count Diff':>10} | Location",
                "-" * 80,
            ]
            for diff in res.get("top_differences", []):
                loc = diff["traceback"][0] if diff["traceback"] else "unknown"
                output.append(
                    f"{diff['size_diff_kb']:12.2f} | {diff['size_kb']:12.2f} | {diff['count_diff']:10d} | {loc}"
                )
                
            self.log_output.setPlainText("\n".join(output))
        finally:
            QApplication.restoreOverrideCursor()
            self._update_ui_state()
