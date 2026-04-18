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

"""Smoke tests for main window construction."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QCheckBox, QLabel, QLineEdit, QMenu, QTreeWidget

from app import build_about_text
from app.indexer.index_manager import IndexManager
from app.ui.main_window import MainWindow


def test_main_window_builds_tabs(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    window = MainWindow(manager)
    qtbot.addWidget(window)

    central = window.centralWidget()
    assert central.count() >= 2
    assert central.tabText(0) == "Search Browser"
    assert central.tabText(1) == "Excel Library"
    assert not window.windowIcon().isNull()


def test_main_window_shows_refresh_indicators_and_toggle(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    window = MainWindow(manager)
    qtbot.addWidget(window)

    indicator_labels = [label.text() for label in window.statusBar().findChildren(QLabel)]
    assert any(text.startswith("Auto-Refresh:") for text in indicator_labels)
    assert any(text.startswith("Skipped:") for text in indicator_labels)
    assert any(text.startswith("Last Refresh:") for text in indicator_labels)

    window._toggle_auto_refresh(False)
    assert not manager.is_refresh_worker_running()
    window._toggle_auto_refresh(True)
    assert manager.is_refresh_worker_running()
    manager.stop_refresh_worker()


def test_main_window_shows_library_navigation_pane(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    window = MainWindow(manager)
    qtbot.addWidget(window)

    library_tree = window.findChild(QTreeWidget, "libraryTree")
    assert library_tree is not None
    assert library_tree.topLevelItemCount() == 4

    root_titles = [library_tree.topLevelItem(index).text(0) for index in range(library_tree.topLevelItemCount())]
    assert root_titles[0].startswith("Files (")
    assert root_titles[1].startswith("Symbols (")
    assert root_titles[2].startswith("Excel Rows (")
    assert root_titles[3].startswith("Skipped Files (")


def test_main_window_exposes_help_menu_and_about_text(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    window = MainWindow(manager)
    qtbot.addWidget(window)

    help_menu = window.findChild(QMenu, "menuHelp")
    assert help_menu is not None
    assert any(action.text() == "About" for action in help_menu.actions())

    about_text = build_about_text()
    assert "PyQt6" in about_text
    assert "folder where the application is opened" in about_text


def test_library_navigation_filter_and_tree_toggle(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    window = MainWindow(manager)
    qtbot.addWidget(window)

    library_tree = window.findChild(QTreeWidget, "libraryTree")
    filter_input = window.findChild(QLineEdit, "libraryFilterInput")
    tree_toggle = window.findChild(QCheckBox, "libraryTreeToggle")

    assert library_tree is not None
    assert filter_input is not None
    assert tree_toggle is not None
    assert tree_toggle.isChecked()

    filter_input.setText("main_window.py")
    files_root = library_tree.topLevelItem(0)
    assert "/" in files_root.text(0)

    tree_toggle.setChecked(False)
    files_root_flat = library_tree.topLevelItem(0)
    if files_root_flat.childCount() > 0:
        assert files_root_flat.child(0).text(1) != ""


def test_library_double_click_opens_file(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    window = MainWindow(manager)
    qtbot.addWidget(window)

    library_tree = window.findChild(QTreeWidget, "libraryTree")
    assert library_tree is not None

    files_root = library_tree.topLevelItem(0)
    assert files_root is not None

    target_item = None

    def walk(item):
        nonlocal target_item
        payload = item.data(0, 0x0100)
        if isinstance(payload, dict) and payload.get("kind") == "file":
            target_item = item
            return
        for idx in range(item.childCount()):
            if target_item is None:
                walk(item.child(idx))

    walk(files_root)
    assert target_item is not None

    opened: dict[str, str] = {}

    def fake_open_url(url):
        opened["path"] = Path(url.toLocalFile()).name
        return True

    monkeypatch.setattr("app.ui.main_window.QDesktopServices.openUrl", fake_open_url)

    window._on_library_item_double_clicked(target_item, 0)
    assert opened.get("path") == "sample.py"
