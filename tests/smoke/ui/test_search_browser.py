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

"""Smoke tests for SearchBrowser interaction and results rendering."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_manager import IndexManager
from app.ui.search_browser import SearchBrowser


def test_search_browser_shows_clickable_results_columns(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    browser = SearchBrowser(manager)
    qtbot.addWidget(browser)

    browser.set_query("sample", scope="all", execute=True)

    assert browser.results_table.columnCount() == 6
    assert not browser.results_table.horizontalHeader().isHidden()
    assert browser.results_table.rowCount() > 0
    first_type = browser.results_table.item(0, 0)
    first_file_type = browser.results_table.item(0, 1)
    assert first_type is not None
    assert first_file_type is not None
    assert first_type.text() != ""
    assert first_file_type.text() != ""


def test_search_browser_shows_line_context_for_selected_result(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.state.file_corpus = {"app/sample.py": "line one\nneedle line\nline three\n"}
    manager.state.symbols = []
    manager.state.excel_rows = []

    widget = SearchBrowser(manager)
    qtbot.addWidget(widget)

    widget.query_input.setText("needle")
    widget.scope_combo.setCurrentText("files")
    widget.run_search()

    preview = widget.preview_pane.toPlainText()
    assert "Path: app/sample.py" in preview
    assert "needle line" in preview


def test_search_browser_double_click_opens_file(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    browser = SearchBrowser(manager)
    qtbot.addWidget(browser)
    browser.set_query("sample", scope="files", execute=True)

    opened: dict[str, str] = {}

    def fake_open_url(url):
        opened["path"] = Path(url.toLocalFile()).name
        return True

    monkeypatch.setattr("app.ui.search_browser.QDesktopServices.openUrl", fake_open_url)

    assert browser.results_table.rowCount() > 0
    browser._on_result_double_clicked(0, 0)
    assert opened.get("path") == "sample.py"
