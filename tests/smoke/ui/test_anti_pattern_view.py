# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#

"""Smoke tests for the AntiPatternView widget."""

from __future__ import annotations

import re
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QDialog

from app.indexer.index_manager import IndexManager
from app.views.anti_pattern_view import AntiPatternView, PresetDialog


def test_anti_pattern_view_loads_and_lists_defaults(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    widget = AntiPatternView(manager)
    qtbot.addWidget(widget)

    # Check default presets loaded
    assert widget.presets_list.count() > 0
    first_item = widget.presets_list.item(0)
    assert "Bare Except" in first_item.text()


def test_anti_pattern_view_scans_code(qtbot, app_config, sample_repo):
    # Add a file with a known anti-pattern (bare except)
    bad_file = sample_repo / "app" / "bad.py"
    bad_file.write_text(
        "def oops():\n"
        "    try:\n"
        "        x = 1 / 0\n"
        "    exce" + "pt:\n"
        "        print('oops')\n",
        encoding="utf-8"
    )

    manager = IndexManager(app_config)
    manager.refresh()

    widget = AntiPatternView(manager)
    qtbot.addWidget(widget)

    # Run the scan
    widget.run_scan()

    # Results table should contain the bare except match
    assert widget.results_table.rowCount() > 0
    found = False
    for row in range(widget.results_table.rowCount()):
        preset_name = widget.results_table.item(row, 2).text()
        if preset_name == "Bare Except":
            found = True
            break
    assert found


def test_anti_pattern_view_adds_preset(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    widget = AntiPatternView(manager)
    qtbot.addWidget(widget)

    initial_count = widget.presets_list.count()

    # Mock PresetDialog execution to accept and return custom inputs
    def mock_exec(self_dialog):
        self_dialog.name_input.setText("Custom Pattern")
        self_dialog.regex_input.setText(r"custom_pattern_regex")
        self_dialog.severity_combo.setCurrentText("warning")
        self_dialog.desc_input.setText("A custom audit pattern desc")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PresetDialog, "exec", mock_exec)

    widget.add_preset()

    assert widget.presets_list.count() == initial_count + 1
    new_item = widget.presets_list.item(initial_count)
    assert "Custom Pattern" in new_item.text()


def test_anti_pattern_view_deletes_preset(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    widget = AntiPatternView(manager)
    qtbot.addWidget(widget)

    initial_count = widget.presets_list.count()
    assert initial_count > 0

    # Select the first item
    widget.presets_list.setCurrentRow(0)

    # Mock the deletion confirmation box
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    widget.delete_preset()
    assert widget.presets_list.count() == initial_count - 1


def test_anti_pattern_view_severity_coloring(qtbot, app_config, sample_repo):
    # Add files triggering different severity levels
    (sample_repo / "app" / "bad_err.py").write_text("eval" + "('1')", encoding="utf-8") # Error
    (sample_repo / "app" / "bad_warn.py").write_text("except" + ":", encoding="utf-8")   # Warning

    manager = IndexManager(app_config)
    manager.refresh()

    widget = AntiPatternView(manager)
    qtbot.addWidget(widget)

    widget.run_scan()
    assert widget.results_table.rowCount() >= 2

    # Verify cell color coding
    colors_found = {}
    for row in range(widget.results_table.rowCount()):
        item = widget.results_table.item(row, 3)
        severity = item.text()
        bg = item.background().color().name()
        colors_found[severity] = bg

    assert "error" in colors_found
    assert "warning" in colors_found
    assert colors_found["error"] == "#fce8e6"
    assert colors_found["warning"] == "#fef7e0"


def test_anti_pattern_view_exports_csv(monkeypatch, qtbot, app_config, tmp_path):
    manager = IndexManager(app_config)
    manager.refresh()

    widget = AntiPatternView(manager)
    qtbot.addWidget(widget)

    # Mock results to export
    widget._last_results = [
        {
            "path": "app/sample.py",
            "line": 10,
            "preset_name": "Test Preset",
            "severity": "warning",
            "match": "test",
            "content": "test line content",
        }
    ]

    target_csv = tmp_path / "results_export.csv"

    # Mock QFileDialog to return our target CSV path
    from PyQt6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target_csv), "CSV Files (*.csv)"))
    # Mock QMessageBox to avoid dialog popup blocking the test
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    widget.export_results_to_csv()

    assert target_csv.exists()
    csv_content = target_csv.read_text(encoding="utf-8")
    assert "Test Preset" in csv_content
    assert "test line content" in csv_content


def test_anti_pattern_view_open_uses_open_file_callback(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    opened: dict[str, object] = {}

    def open_in_app(path: Path, line_number: int | None) -> bool:
        opened["path"] = path.name
        opened["line"] = line_number
        return True

    widget = AntiPatternView(manager, open_file_callback=open_in_app)
    qtbot.addWidget(widget)

    widget._open_result_file({"path": "app/sample.py", "line": 2})
    assert opened.get("path") == "sample.py"
    assert opened.get("line") == 2
