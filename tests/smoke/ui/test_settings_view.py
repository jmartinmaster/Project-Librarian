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
"""Smoke tests for settings dialog editable list controls."""

from __future__ import annotations

from pathlib import Path

from app.config import AppConfig
from app.views.settings_view import SettingsView


def test_settings_view_add_remove_extension_and_excluded_dir(qtbot):
    config = AppConfig()
    dialog = SettingsView(config)
    qtbot.addWidget(dialog)

    initial_extensions = dialog.extensions_list.count()
    dialog.extension_input.setText("toml")
    dialog._add_extension()
    assert dialog.extensions_list.count() == initial_extensions + 1

    added_item = dialog.extensions_list.item(dialog.extensions_list.count() - 1)
    added_item.setSelected(True)
    dialog._remove_extension()
    assert dialog.extensions_list.count() == initial_extensions

    initial_excluded = dialog.excluded_list.count()
    dialog.excluded_input.setText("cache")
    dialog._add_excluded_dir()
    assert dialog.excluded_list.count() == initial_excluded + 1

    added_excluded = dialog.excluded_list.item(dialog.excluded_list.count() - 1)
    added_excluded.setSelected(True)
    dialog._remove_excluded_dir()
    assert dialog.excluded_list.count() == initial_excluded


def test_settings_view_allows_zero_refresh_interval(monkeypatch, qtbot, tmp_path: Path):
    config = AppConfig(refresh_interval_seconds=30)
    dialog = SettingsView(config)
    qtbot.addWidget(dialog)

    written = {}

    def fake_save_config(saved_config):
        written["interval"] = saved_config.refresh_interval_seconds
        return tmp_path / "config.json"

    monkeypatch.setattr("app.controllers.settings_controller.save_config", fake_save_config)

    dialog.refresh_spin.setValue(0)
    dialog._save_and_accept()

    assert config.refresh_interval_seconds == 0
    assert written["interval"] == 0


def test_settings_view_indexing_thread_count_roundtrip(monkeypatch, qtbot, tmp_path: Path):
    config = AppConfig(indexing_thread_count=4)
    dialog = SettingsView(config)
    qtbot.addWidget(dialog)

    written = {}

    def fake_save_config(saved_config):
        written["indexing_thread_count"] = saved_config.indexing_thread_count
        return tmp_path / "config.json"

    monkeypatch.setattr("app.controllers.settings_controller.save_config", fake_save_config)

    # Verify initial value
    assert dialog.thread_count_spin.value() == 4

    # Verify range [1, 24]
    assert dialog.thread_count_spin.minimum() == 1
    assert dialog.thread_count_spin.maximum() == 24

    # Update value and save
    dialog.thread_count_spin.setValue(8)
    dialog._save_and_accept()

    assert config.indexing_thread_count == 8
    assert written["indexing_thread_count"] == 8


def test_settings_view_incremental_and_cst_guard_controls(monkeypatch, qtbot, tmp_path: Path):
    config = AppConfig(
        cst_max_file_size_kb=200,
        cst_excluded_paths=["generated/"],
        incremental_indexing=True,
        search_result_limit=100,
        search_debounce_ms=300,
    )
    dialog = SettingsView(config)
    qtbot.addWidget(dialog)

    assert dialog.cst_max_file_size_spin.value() == 200
    assert dialog.incremental_indexing_check.isChecked() is True
    assert dialog.search_limit_spin.value() == 100
    assert dialog.search_debounce_spin.value() == 300
    assert dialog.cst_excluded_list.count() == 1
    assert dialog.cst_excluded_list.item(0).text() == "generated/"

    # Add/remove CST excluded item
    dialog.cst_excluded_input.setText("large_data.py")
    dialog._add_cst_excluded()
    assert dialog.cst_excluded_list.count() == 2

    dialog.cst_excluded_list.item(1).setSelected(True)
    dialog._remove_cst_excluded()
    assert dialog.cst_excluded_list.count() == 1

    # Test presets
    initial_excl = dialog.excluded_list.count()
    dialog._add_default_exclusions()
    assert dialog.excluded_list.count() >= initial_excl

    initial_exts = dialog.extensions_list.count()
    dialog._add_common_extensions()
    assert dialog.extensions_list.count() >= initial_exts

    # Update values and save
    dialog.cst_max_file_size_spin.setValue(500)
    dialog.incremental_indexing_check.setChecked(False)
    dialog.search_limit_spin.setValue(250)
    dialog.search_debounce_spin.setValue(500)

    written = {}

    def fake_save_config(saved_config):
        written["saved"] = saved_config
        return tmp_path / "config.json"

    monkeypatch.setattr("app.controllers.settings_controller.save_config", fake_save_config)
    dialog._save_and_accept()

    assert config.cst_max_file_size_kb == 500
    assert config.incremental_indexing is False
    assert config.search_result_limit == 250
    assert config.search_debounce_ms == 500


