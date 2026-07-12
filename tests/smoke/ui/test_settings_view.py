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

