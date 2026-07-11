# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#

"""Diagnostics and memory profiling manager widget with visualizations."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt, QPointF, QRectF, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QProgressDialog,
    QTabWidget,
    QFrame,
    QProgressBar,
)
import sys

from app.controllers.diagnostics_controller import DiagnosticsController
from app.indexer.index_manager import IndexManager
from app.models.diagnostics_model import DiagnosticsModel
from app.views.diagnostics_runner import DiagnosticsRunner


class PipInstallWorker(QThread):
    """Worker thread to run pip install asynchronously."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, package_name: str, controller: DiagnosticsController) -> None:
        super().__init__()
        self.package_name = package_name
        self._controller = controller

    def run(self) -> None:
        success, message = self._controller.install_package(self.package_name)
        self.finished_signal.emit(success, message)


class MemoryChartWidget(QWidget):
    """Custom QWidget to paint a beautiful line chart showing memory usage over time."""
    point_clicked = pyqtSignal(int, str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history: list[tuple[str, float]] = []
        self.selected_index: int = -1
        self._drawn_points: list[tuple[QPointF, int]] = []
        self.setMinimumHeight(155)

    def set_history(self, history: list[tuple[str, float]], color: str = "#1a73e8") -> None:
        self.history = history
        self.line_color = color
        self.selected_index = -1
        self.update()

    def mousePressEvent(self, event) -> None:
        if not self.history or not self._drawn_points:
            return
        
        click_pos = event.position() if hasattr(event, "position") else event.pos()
        closest_idx = -1
        min_dist = 100.0
        
        for pt, idx in self._drawn_points:
            dist = ((pt.x() - click_pos.x())**2 + (pt.y() - click_pos.y())**2)**0.5
            if dist < min_dist:
                min_dist = dist
                closest_idx = idx
                
        if closest_idx != -1 and min_dist < 10.0:
            self.selected_index = closest_idx
            self.update()
            name, size = self.history[closest_idx]
            self.point_clicked.emit(closest_idx, name, size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Background
        painter.fillRect(0, 0, width, height, QColor("#1e1e24"))

        if not self.history:
            painter.setPen(QColor("#808080"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No memory snapshots recorded yet.\nTake snapshots to see the chart.",
            )
            return

        # Margins
        margin_left = 65
        margin_right = 20
        margin_top = 20
        margin_bottom = 30

        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        sizes = [size for _, size in self.history]
        max_val = max(sizes) * 1.15 if sizes else 10.0
        min_val = min(sizes) * 0.85 if sizes else 0.0
        if max_val == min_val:
            max_val += 10.0
            min_val = max(0.0, min_val - 10.0)

        val_range = max_val - min_val

        # Draw grid lines & axes
        grid_pen = QPen(QColor("#3a3a45"), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)

        # Horizontal grid lines (4 levels)
        for i in range(4):
            y = margin_top + plot_h * (i / 3)
            painter.drawLine(margin_left, int(y), width - margin_right, int(y))

            # Y label
            val = max_val - val_range * (i / 3)
            painter.setPen(QColor("#a0a0b0"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(5, y - 8, margin_left - 10, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{val:.1f} KB",
            )
            painter.setPen(grid_pen)

        # Draw the line and points
        points = []
        for idx, (name, size) in enumerate(self.history):
            x = margin_left + (plot_w * (idx / (len(self.history) - 1)) if len(self.history) > 1 else plot_w / 2)
            y = margin_top + plot_h * (1.0 - (size - min_val) / val_range)
            points.append(QPointF(x, y))

        self._drawn_points = [(pt, idx) for idx, pt in enumerate(points)]

        # Draw gradient area under the line
        if len(points) > 1:
            gradient = QLinearGradient(0, margin_top, 0, height - margin_bottom)
            base_color = QColor(getattr(self, "line_color", "#1a73e8"))
            gradient.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 100))
            gradient.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 0))

            path_points = (
                [QPointF(margin_left, height - margin_bottom)]
                + points
                + [QPointF(points[-1].x(), height - margin_bottom)]
            )
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(path_points)

        # Draw the line itself
        line_pen = QPen(QColor(getattr(self, "line_color", "#1a73e8")), 2, Qt.PenStyle.SolidLine)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for idx in range(len(points) - 1):
            painter.drawLine(points[idx], points[idx + 1])

        # Draw points and labels
        for idx, pt in enumerate(points):
            name, size = self.history[idx]

            # If selected, draw highlight ring first
            if self.selected_index == idx:
                painter.setPen(QPen(QColor("#f1c40f"), 3.0)) # Golden ring
                painter.setBrush(QBrush(QColor(getattr(self, "line_color", "#1a73e8"))))
                painter.drawEllipse(pt, 8, 8)

            # Point circle
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QBrush(QColor(getattr(self, "line_color", "#1a73e8"))))
            painter.drawEllipse(pt, 4, 4)

            if len(self.history) < 10 or idx == 0 or idx == len(self.history) - 1 or idx % max(1, len(self.history) // 5) == 0:
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(QRectF(pt.x() - 30, pt.y() - 18, 60, 12), Qt.AlignmentFlag.AlignCenter, f"{size:.0f}K")

                # Bottom X Label
                painter.setPen(QColor("#a0a0b0"))
                painter.setFont(QFont("Segoe UI", 7))
                short_name = name.split("_")[-1] if "snapshot_" in name else name
                painter.drawText(
                    QRectF(pt.x() - 40, height - margin_bottom + 4, 80, 20),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    short_name,
                )


class DiagnosticsView(QWidget):
    """Widget providing memory tracing controls and PyQt6 leak detection."""

    def __init__(self, index_manager: IndexManager) -> None:
        super().__init__()
        self.index_manager = index_manager
        self._controller = DiagnosticsController()
        
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

        self.service: DiagnosticsModel | None = None
        self.runner: DiagnosticsRunner | None = None
        self.memory_history: list[tuple[str, float]] = []
        self.external_history: list[tuple[str, float]] = []
        self._last_comparison_results: list[dict[str, object]] = []

        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._on_progress_tick)
        self.elapsed_seconds = 0
        self.target_duration = 0
        self.has_custom_selection = False

        self._load_ui()
        self._build_ui()
        self._init_model()
        self._update_ui_state()

    def _load_ui(self) -> None:
        """Load and bind the diagnostics Designer form."""
        ui_path = Path(__file__).resolve().parent / "forms" / "diagnostics_view.ui"
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

        self.main_splitter = self.findChild(QSplitter, "mainSplitter")
        self.controls_layout = self.findChild(QVBoxLayout, "controlsLayout")

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

        # Build External Target Script programmatically
        if self.controls_layout:
            run_btn_idx = -1
            for i in range(self.controls_layout.count()):
                item = self.controls_layout.itemAt(i)
                if item and item.widget() == self.run_leak_test_btn:
                    run_btn_idx = i
                    break
            
            row1 = QHBoxLayout()
            self.target_script_input = QLineEdit(self)
            self.target_script_input.setPlaceholderText("Target script to profile (optional)")
            self.target_script_input.setObjectName("targetScriptInput")
            
            self.target_script_browse_btn = QPushButton("Browse...", self)
            self.target_script_browse_btn.setObjectName("targetScriptBrowseBtn")
            self.target_script_browse_btn.clicked.connect(self.browse_target_script)
            
            row1.addWidget(self.target_script_input)
            row1.addWidget(self.target_script_browse_btn)

            row2 = QHBoxLayout()
            self.target_duration_spin = QSpinBox(self)
            self.target_duration_spin.setRange(0, 3600)
            self.target_duration_spin.setValue(0)
            self.target_duration_spin.setToolTip("Run duration in seconds (0 = run until closed)")
            
            self.target_interval_spin = QSpinBox(self)
            self.target_interval_spin.setRange(0, 600)
            self.target_interval_spin.setValue(5)
            self.target_interval_spin.setToolTip("Live snapshot interval in seconds (0 = disabled)")
            
            self.target_headless_check = QCheckBox("Headless", self)
            self.target_headless_check.setChecked(False)
            self.target_headless_check.setToolTip("Force GUI offscreen")
            
            row2.addWidget(QLabel("Timer (s):", self))
            row2.addWidget(self.target_duration_spin)
            row2.addWidget(QLabel("Int. (s):", self))
            row2.addWidget(self.target_interval_spin)
            row2.addWidget(self.target_headless_check)
            
            target_layout = QVBoxLayout()
            target_layout.addLayout(row1)
            target_layout.addLayout(row2)
            
            if run_btn_idx != -1:
                self.controls_layout.insertLayout(run_btn_idx, target_layout)
            else:
                self.controls_layout.addLayout(target_layout)

        # Build Memory Chart Layout programmatically
        if self.main_splitter:
            idx = self.main_splitter.indexOf(self.log_output)
            right_container = QWidget(self.main_splitter)
            right_layout = QVBoxLayout(right_container)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(6)

            self.chart_tabs = QTabWidget(right_container)
            self.internal_chart = MemoryChartWidget(self.chart_tabs)
            self.external_chart = MemoryChartWidget(self.chart_tabs)
            
            self.chart_tabs.addTab(self.internal_chart, "Librarian Memory")
            self.chart_tabs.addTab(self.external_chart, "Target Script Memory")
            
            self.internal_chart.point_clicked.connect(self._on_chart_point_clicked)
            self.external_chart.point_clicked.connect(self._on_chart_point_clicked)
            self.chart_tabs.currentChanged.connect(self._on_tab_changed)
            
            right_layout.addWidget(self.chart_tabs)

            # Real-time stats panel
            self.stats_panel = QFrame(right_container)
            self.stats_panel.setObjectName("statsPanel")
            self.stats_panel.setFrameShape(QFrame.Shape.StyledPanel)
            self.stats_panel.setStyleSheet("""
                QFrame#statsPanel {
                    background-color: #1e1e24;
                    border: 1px solid #33333d;
                    border-radius: 6px;
                    padding: 4px;
                }
                QLabel {
                    color: #e0e0e0;
                    font-size: 11px;
                }
                QProgressBar {
                    border: 1px solid #33333d;
                    border-radius: 4px;
                    text-align: center;
                    color: #ffffff;
                    background-color: #121214;
                    font-size: 10px;
                    height: 14px;
                }
                QProgressBar::chunk {
                    background-color: #e8731a;
                    border-radius: 3px;
                }
            """)
            stats_layout = QHBoxLayout(self.stats_panel)
            stats_layout.setContentsMargins(8, 4, 8, 4)
            stats_layout.setSpacing(12)

            self.stat_base_lbl = QLabel("Base: -- KB", self.stats_panel)
            self.stat_selected_lbl = QLabel("Selected: -- KB", self.stats_panel)
            self.stat_curr_lbl = QLabel("Latest: -- KB", self.stats_panel)
            self.stat_growth_lbl = QLabel("Growth: -- KB", self.stats_panel)

            self.stat_base_lbl.setStyleSheet("font-weight: bold; color: #a0a0b0;")
            self.stat_selected_lbl.setStyleSheet("font-weight: bold; color: #f1c40f;")
            self.stat_curr_lbl.setStyleSheet("font-weight: bold; color: #e8731a;")
            self.stat_growth_lbl.setStyleSheet("font-weight: bold;")

            stats_layout.addWidget(self.stat_base_lbl)
            stats_layout.addWidget(self.stat_selected_lbl)
            stats_layout.addWidget(self.stat_curr_lbl)
            stats_layout.addWidget(self.stat_growth_lbl)

            stats_layout.addStretch(1)

            # Timer and Progress Bar on the right
            self.stat_time_lbl = QLabel("Time: 00:00 / 00:00", self.stats_panel)
            self.stat_time_lbl.setStyleSheet("font-family: Consolas, monospace; color: #a0a0b0;")
            self.stat_progress_bar = QProgressBar(self.stats_panel)
            self.stat_progress_bar.setFixedWidth(150)
            self.stat_progress_bar.setValue(0)

            stats_layout.addWidget(self.stat_time_lbl)
            stats_layout.addWidget(self.stat_progress_bar)

            right_layout.addWidget(self.stats_panel)
            
            # Hide progress elements by default
            self.stat_time_lbl.hide()
            self.stat_progress_bar.hide()

            # Reparent log output to container
            self.log_output.setParent(right_container)
            right_layout.addWidget(self.log_output)

            # Adjust stretches: tabs, stats panel, log output
            right_layout.setStretch(0, 4)
            right_layout.setStretch(1, 0)
            right_layout.setStretch(2, 6)

            self.main_splitter.insertWidget(idx, right_container)

        # Build Export Compare button programmatically
        if self.controls_layout:
            btn_idx = -1
            for i in range(self.controls_layout.count()):
                item = self.controls_layout.itemAt(i)
                if item.widget() == self.compare_btn:
                    btn_idx = i
                    break

            self.export_compare_btn = QPushButton("Export Compare to CSV...", self)
            self.export_compare_btn.setObjectName("exportCompareBtn")
            self.export_compare_btn.setEnabled(False)
            self.export_compare_btn.clicked.connect(self.export_comparison_to_csv)

            if btn_idx != -1:
                self.controls_layout.insertWidget(btn_idx + 1, self.export_compare_btn)
            else:
                self.controls_layout.addWidget(self.export_compare_btn)

    def _init_model(self) -> None:
        try:
            self.service = DiagnosticsModel()
            baseline_history, _ = self._controller.initialize_diagnostics_state(self.service)
            self.memory_history.extend(baseline_history)
        except Exception as exc:
            self.service = None
            self.log_output.setPlainText(
                f"Failed to initialize Diagnostics Model:\n{exc}\n\n"
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
            if hasattr(self, "export_compare_btn"):
                self.export_compare_btn.setEnabled(False)
            return
        
        status = self._controller.tracing_status(self.service)
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
        if hasattr(self, "export_compare_btn"):
            self.export_compare_btn.setEnabled(len(self._last_comparison_results) > 0)

        # Sync memory history to saved snapshots
        self.memory_history = [(name, val) for name, val in self.memory_history if name in saved]
        if hasattr(self, "internal_chart") and self.internal_chart:
            sel_idx = self.internal_chart.selected_index
            self.internal_chart.set_history(self.memory_history)
            if self.has_custom_selection and sel_idx != -1:
                self.internal_chart.selected_index = sel_idx
                self.internal_chart.update()
        
        self._update_hud_stats()

    def start_tracing(self) -> None:
        """Start memory tracing."""
        if not self.service:
            return
        res = self._controller.start_tracing(self.service, n_frames=25)
        self.log_output.setPlainText(res.get("message", "Started tracing."))
        self.memory_history.clear()
        self._update_ui_state()

    def stop_tracing(self) -> None:
        """Stop memory tracing and clear snapshots."""
        if not self.service:
            return
        res = self._controller.stop_tracing(self.service)
        self.log_output.setPlainText(res.get("message", "Stopped tracing."))
        self.memory_history.clear()
        self._last_comparison_results = []
        self._update_ui_state()

    def take_snapshot(self) -> None:
        """Record current memory allocation snapshot state."""
        if not self.service:
            return
        name = self.snapshot_name.text().strip() or None
        self.snapshot_name.clear()
        
        res = self._controller.take_snapshot(self.service, snapshot_name=name)
        if not res.get("ok"):
            self.log_output.setPlainText(res.get("error", "Failed to take snapshot."))
            return
             
        snap_name = res.get("snapshot_name")
        size_kb = res.get("total_allocated_kb", 0.0)
        self.memory_history.append((snap_name, size_kb))
        self.log_output.setPlainText(self._controller.snapshot_result_text(res))
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

        res = self._controller.compare_snapshots(self.service, old_snapshot=old_name, new_snapshot=new_name)
        if not res.get("ok", True):
            self.log_output.setPlainText(res.get("error", "Comparison failed."))
            self._last_comparison_results = []
            if hasattr(self, "export_compare_btn"):
                self.export_compare_btn.setEnabled(False)
            return

        self._last_comparison_results = res.get("top_differences", [])
        if hasattr(self, "export_compare_btn"):
            self.export_compare_btn.setEnabled(len(self._last_comparison_results) > 0)
        self.log_output.setPlainText(self._controller.comparison_result_text(res, self._last_comparison_results))

    def export_comparison_to_csv(self) -> None:
        """Export the latest snapshot comparison differences to a CSV file."""
        if not hasattr(self, "_last_comparison_results") or not self._last_comparison_results:
            QMessageBox.warning(self, "No Comparison Data", "Please run a comparison first before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Allocation Differences to CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        try:
            self._controller.export_comparison_to_csv(self._last_comparison_results, file_path)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Successfully exported allocation differences to:\n{file_path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Failed to export: {exc}")

    def browse_target_script(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Target Script",
            "",
            "Python Scripts (*.py);;All Files (*)",
        )
        if file_path:
            self.target_script_input.setText(file_path)

    def run_leak_test(self) -> None:
        """Run headless IndexManager profiling in a sandboxed subprocess."""
        if not self.service:
            return
            
        if self.run_leak_test_btn.text() == "Cancel":
            if hasattr(self, "runner"):
                self.runner.kill()
                self.log_output.appendPlainText("\n[Test Cancelled by User]")
            self.run_leak_test_btn.setText("Run Leak Test")
            QApplication.restoreOverrideCursor()
            self.progress_timer.stop()
            return
            
        target_path = None
        duration = 0
        interval = 0
        headless = False
        
        if hasattr(self, "target_script_input") and self.target_script_input.text().strip():
            target_path = self.target_script_input.text().strip()
            duration = self.target_duration_spin.value()
            interval = self.target_interval_spin.value()
            headless = self.target_headless_check.isChecked()
            
        msg = self._controller.profiling_start_message(
            target_path=target_path,
            duration=duration,
            interval=interval,
            headless=headless,
        )
        self.log_output.setPlainText(msg)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        self.run_leak_test_btn.setText("Cancel")
        self.external_history = []
        if hasattr(self, "external_chart") and self.external_chart:
            self.external_chart.set_history([], color="#e8731a")
            if hasattr(self, "chart_tabs"):
                self.chart_tabs.setCurrentWidget(self.external_chart)
                
        # Initialize stats panel
        self.stat_base_lbl.setText("Base: -- KB")
        self.stat_selected_lbl.setText("Selected: -- KB")
        self.stat_curr_lbl.setText("Latest: -- KB")
        self.stat_growth_lbl.setText("Growth: -- KB")
        self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        self.has_custom_selection = False
        
        if target_path:
            self.stat_time_lbl.show()
            self.stat_progress_bar.show()
            self.target_duration = duration
            self.elapsed_seconds = 0
            if duration > 0:
                self.stat_progress_bar.setRange(0, 100)
                self.stat_progress_bar.setValue(0)
                total_m, total_s = divmod(duration, 60)
                self.stat_time_lbl.setText(f"Time: 00:00 / {total_m:02d}:{total_s:02d}")
            else:
                self.stat_progress_bar.setRange(0, 0)
                self.stat_time_lbl.setText("Time: 00:00")
            self.progress_timer.start(1000)
            
        self.runner = DiagnosticsRunner(self)
        self.runner.start_profile(target_path, duration=duration, interval=interval, headless=headless)
        
        def on_output(text: str):
            self.log_output.appendPlainText(text)
            
        def on_live_snapshot(data: dict):
            if "name" in data and "size_kb" in data:
                size_kb = data["size_kb"]
                self.external_history.append((data["name"], size_kb))
                
                # We want to preserve the selected index visual highlight when setting history
                # But since set_history resets selected_index to -1, we restore it if has_custom_selection is True
                sel_idx = -1
                if hasattr(self, "external_chart") and self.external_chart:
                    sel_idx = self.external_chart.selected_index
                    self.external_chart.set_history(self.external_history, color="#e8731a")
                    if self.has_custom_selection and sel_idx != -1:
                        self.external_chart.selected_index = sel_idx
                        self.external_chart.update()
                
                # Update stats HUD labels
                if self.external_history:
                    base_kb = self.external_history[0][1]
                    curr_kb = size_kb
                    
                    self.stat_base_lbl.setText(f"Base: {base_kb:,.2f} KB")
                    self.stat_curr_lbl.setText(f"Latest: {curr_kb:,.2f} KB")
                    
                    if not self.has_custom_selection:
                        self.stat_selected_lbl.setText(f"Selected: {curr_kb:,.2f} KB")
                    
                    growth_kb = curr_kb - base_kb
                    pct = (growth_kb / base_kb * 100) if base_kb > 0 else 0.0
                    sign = "+" if growth_kb >= 0 else ""
                    self.stat_growth_lbl.setText(f"Growth: {sign}{growth_kb:,.2f} KB ({sign}{pct:.1f}%)")
                    if growth_kb > 0:
                        self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #ff4d4d;")
                    elif growth_kb < 0:
                        self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #2ecc71;")
                    else:
                        self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
            
        def on_error(err: str):
            self.log_output.appendPlainText(f"\n[Error] {err}")
            
        def on_finished(exit_code: int):
            self.progress_timer.stop()
            if hasattr(self, "stat_time_lbl"):
                self.stat_time_lbl.hide()
            if hasattr(self, "stat_progress_bar"):
                self.stat_progress_bar.hide()
            QApplication.restoreOverrideCursor()
            self.run_leak_test_btn.setText("Run Leak Test")
            self._update_ui_state()
            
            if exit_code != 0:
                self.log_output.appendPlainText(f"\nProcess exited with code {exit_code}")
                
        def on_profiling_completed(result: dict):
            QApplication.restoreOverrideCursor()
            self.run_leak_test_btn.setText("Run Leak Test")
            self._update_ui_state()
                
            if not result:
                self.log_output.appendPlainText("\nNo profiling results returned.")
                return

            if result.get("error"):
                err_msg = result["error"]
                self.log_output.appendPlainText(f"\n[Execution Error]\n{err_msg}")
                
                # Check for ModuleNotFoundError
                module_name = self._controller.missing_module_name(err_msg)
                if module_name:
                    default_pkg = self._controller.suggested_package_name(module_name)
                    
                    pkg_name, ok = QInputDialog.getText(
                        self,
                        "Missing Module Detected",
                        f"Target script crashed because module '{module_name}' is missing.\n\n"
                        f"Do you want to install it into Project Librarian's environment?\n"
                        f"(Note: Please search PyPI if you do not know the correct package name for this module)\n\n"
                        f"Package name to install:",
                        QLineEdit.EchoMode.Normal,
                        default_pkg
                    )
                    
                    if ok and pkg_name.strip():
                        pkg_to_install = pkg_name.strip()
                        self.log_output.appendPlainText(f"\n[Pip] Installing '{pkg_to_install}'...")
                        
                        progress = QProgressDialog(f"Installing '{pkg_to_install}' via pip...", None, 0, 0, self)
                        progress.setWindowTitle("Installing Dependencies")
                        progress.setWindowModality(Qt.WindowModality.WindowModal)
                        progress.setCancelButton(None)
                        progress.show()
                        
                        self.install_worker = PipInstallWorker(pkg_to_install, self._controller)
                        def on_install_finished(success: bool, msg: str):
                            progress.accept()
                            if success:
                                self.log_output.appendPlainText(f"\n[Pip] Successfully installed '{pkg_to_install}'. Retrying leak test...\n")
                                self.run_leak_test()
                            else:
                                QMessageBox.critical(self, "Installation Failed", f"Failed to install '{pkg_to_install}':\n\n{msg}")
                                self.log_output.appendPlainText(f"\n[Pip] Failed to install '{pkg_to_install}'.")
                                
                        self.install_worker.finished_signal.connect(on_install_finished)
                        self.install_worker.start()
                        return
                
                QMessageBox.critical(self, "Target Script Error", f"The target script encountered an error during execution:\n\n{err_msg}")

            self.log_output.appendPlainText(self._controller.profiling_result_text(result))
            
            if self.runner and self.runner.target_path:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Profiling Finished")
                msg_box.setText("Profiling Completed. The target script is still running in the background.\n\nWould you like to terminate it now or leave it running?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                terminate_btn = msg_box.addButton("Terminate", QMessageBox.ButtonRole.DestructiveRole)
                leave_btn = msg_box.addButton("Leave Running", QMessageBox.ButtonRole.AcceptRole)
                msg_box.exec()
                
                if msg_box.clickedButton() == terminate_btn:
                    self.runner.kill()
                    self.log_output.appendPlainText("\n[Target Terminated]")
                else:
                    self.log_output.appendPlainText("\n[Target Left Running]")

        self.runner.output_received.connect(on_output)
        self.runner.error_occurred.connect(on_error)
        self.runner.finished.connect(on_finished)
        self.runner.profiling_completed.connect(on_profiling_completed)
        self.runner.live_snapshot_taken.connect(on_live_snapshot)

    def _on_progress_tick(self) -> None:
        self.elapsed_seconds += 1
        if self.target_duration > 0:
            pct = min(100, int((self.elapsed_seconds / self.target_duration) * 100))
            self.stat_progress_bar.setValue(pct)
            
            elapsed_m, elapsed_s = divmod(self.elapsed_seconds, 60)
            total_m, total_s = divmod(self.target_duration, 60)
            self.stat_time_lbl.setText(f"Time: {elapsed_m:02d}:{elapsed_s:02d} / {total_m:02d}:{total_s:02d}")
        else:
            self.stat_progress_bar.setRange(0, 0)
            elapsed_m, elapsed_s = divmod(self.elapsed_seconds, 60)
            self.stat_time_lbl.setText(f"Time: {elapsed_m:02d}:{elapsed_s:02d}")

    def _on_tab_changed(self, index: int) -> None:
        # Reset custom selection for the new tab
        self.has_custom_selection = False
        
        # Clear selected highlight in both charts
        if hasattr(self, "internal_chart") and self.internal_chart:
            self.internal_chart.selected_index = -1
            self.internal_chart.update()
        if hasattr(self, "external_chart") and self.external_chart:
            self.external_chart.selected_index = -1
            self.external_chart.update()
            
        # Update HUD stats
        self._update_hud_stats()

    def _on_chart_point_clicked(self, idx: int, name: str, size: float) -> None:
        self.has_custom_selection = True
        self._update_hud_stats()

    def _update_hud_stats(self) -> None:
        if not hasattr(self, "chart_tabs"):
            return
            
        is_internal = (self.chart_tabs.currentWidget() == self.internal_chart)
        history = self.memory_history if is_internal else self.external_history
        
        if history:
            base_kb = history[0][1]
            curr_kb = history[-1][1]
            
            self.stat_base_lbl.setText(f"Base: {base_kb:,.2f} KB")
            self.stat_curr_lbl.setText(f"Latest: {curr_kb:,.2f} KB")
            
            # Selected size
            active_chart = self.internal_chart if is_internal else self.external_chart
            if self.has_custom_selection and active_chart.selected_index != -1:
                sel_idx = active_chart.selected_index
                if sel_idx < len(history):
                    sel_kb = history[sel_idx][1]
                    short_name = history[sel_idx][0].split("_")[-1] if "snapshot_" in history[sel_idx][0] else history[sel_idx][0]
                    self.stat_selected_lbl.setText(f"Selected ({short_name}): {sel_kb:,.2f} KB")
                else:
                    self.stat_selected_lbl.setText(f"Selected: {curr_kb:,.2f} KB")
            else:
                self.stat_selected_lbl.setText(f"Selected: {curr_kb:,.2f} KB")
                
            growth_kb = curr_kb - base_kb
            pct = (growth_kb / base_kb * 100) if base_kb > 0 else 0.0
            sign = "+" if growth_kb >= 0 else ""
            self.stat_growth_lbl.setText(f"Growth: {sign}{growth_kb:,.2f} KB ({sign}{pct:.1f}%)")
            
            if growth_kb > 0:
                self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #ff4d4d;")
            elif growth_kb < 0:
                self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #2ecc71;")
            else:
                self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        else:
            self.stat_base_lbl.setText("Base: -- KB")
            self.stat_selected_lbl.setText("Selected: -- KB")
            self.stat_curr_lbl.setText("Latest: -- KB")
            self.stat_growth_lbl.setText("Growth: -- KB")
            self.stat_growth_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0;")
