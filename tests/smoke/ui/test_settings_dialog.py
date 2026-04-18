"""Smoke tests for settings dialog editable list controls."""

from __future__ import annotations

from app.config import AppConfig
from app.ui.settings_dialog import SettingsDialog


def test_settings_dialog_add_remove_extension_and_excluded_dir(qtbot):
    config = AppConfig()
    dialog = SettingsDialog(config)
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
