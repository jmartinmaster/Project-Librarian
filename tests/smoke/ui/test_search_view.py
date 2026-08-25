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
"""Smoke tests for SearchView interaction and results rendering."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_manager import IndexManager
from app.views.search_view import SearchView


def test_search_view_shows_clickable_results_columns(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    browser = SearchView(manager)
    qtbot.addWidget(browser)

    browser.set_query("sample", scope="all", execute=True)

    assert browser.results_table.columnCount() == 7
    assert not browser.results_table.horizontalHeader().isHidden()
    assert browser.results_table.rowCount() > 0
    headers = [browser.results_table.horizontalHeaderItem(i).text() for i in range(7)]
    assert headers == ["Title", "File", "Path", "Line", "Type", "File Type", "Preview"]
    first_title = browser.results_table.item(0, 0)
    first_file = browser.results_table.item(0, 1)
    first_path = browser.results_table.item(0, 2)
    assert first_title is not None and first_title.text() != ""
    assert first_file is not None and first_file.text() != ""
    assert first_path is not None and first_path.text() != ""


def test_search_view_shows_line_context_for_selected_result(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.state.file_corpus = {"app/sample.py": "line one\nneedle line\nline three\n"}
    manager.state.symbols = []
    manager.state.excel_rows = []

    widget = SearchView(manager)
    qtbot.addWidget(widget)

    widget.query_input.setText("needle")
    widget.scope_combo.setCurrentText("files")
    widget.run_search(synchronous=True)

    preview = widget.preview_pane.toPlainText()
    assert "Path: app/sample.py" in preview
    assert "needle line" in preview
    assert "Found 1 match" in widget.stats_label.text()


def test_search_view_double_click_opens_file(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    browser = SearchView(manager)
    qtbot.addWidget(browser)
    browser.set_query("sample", scope="files", execute=True)

    opened: dict[str, str] = {}

    def fake_open_url(url):
        opened["path"] = Path(url.toLocalFile()).name
        return True

    monkeypatch.setattr("app.controllers.search_controller.SearchController.open_external_editor", lambda *args: False)
    monkeypatch.setattr("app.views.search_view.QDesktopServices.openUrl", fake_open_url)

    assert browser.results_table.rowCount() > 0
    browser._on_result_double_clicked(0, 0)
    assert opened.get("path") == "sample.py"


def test_search_view_double_click_uses_open_file_callback(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    opened: dict[str, object] = {}

    def open_in_app(path: Path, line_number: int | None) -> bool:
        opened["path"] = path.name
        opened["line"] = line_number
        return True

    browser = SearchView(manager, open_file_callback=open_in_app)
    qtbot.addWidget(browser)
    browser.set_query("sample", scope="files", execute=True)

    monkeypatch.setattr(
        "app.controllers.search_controller.SearchController.open_external_editor",
        lambda *args: (_ for _ in ()).throw(AssertionError("fallback used")),
    )

    assert browser.results_table.rowCount() > 0
    browser._on_result_double_clicked(0, 0)
    assert opened.get("path") == "sample.py"


def test_search_view_create_note_signal(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.refresh()

    browser = SearchView(manager)
    qtbot.addWidget(browser)
    browser.set_query("sample", scope="files", execute=True)

    received_notes = []
    browser.create_note_requested.connect(lambda f, l, s, src, t, snip: received_notes.append((f, l, s, src, t, snip)))

    # Simulate emitting or context note action
    assert len(browser._last_results) > 0
    res = browser._last_results[0]
    browser.create_note_requested.emit(
        str(res.get("path", "")),
        int(res.get("line") or 1),
        str(res.get("title", "")),
        "Search Browser",
        f"Edit {res.get('title')}",
        str(res.get("preview", "")),
    )

    assert len(received_notes) == 1
    assert "sample.py" in received_notes[0][0]
    assert received_notes[0][3] == "Search Browser"


def test_search_view_live_search_updates_as_you_type(qtbot, app_config):
    manager = IndexManager(app_config)
    manager.state.file_corpus = {"app/sample.py": "line one\nneedle line\nline three\n"}
    manager.state.symbols = []
    manager.state.excel_rows = []

    widget = SearchView(manager)
    qtbot.addWidget(widget)

    # Initial state should be 0 rows
    assert widget.results_table.rowCount() == 0

    # Type into the query input
    widget.query_input.setText("needle")
    assert widget._search_timer.isActive()

    # Wait for debounce timer (300ms) to fire
    qtbot.waitUntil(lambda: widget.results_table.rowCount() > 0, timeout=1000)
    assert widget.results_table.rowCount() == 1

    # Clear query
    widget.query_input.setText("")
    qtbot.waitUntil(lambda: widget.results_table.rowCount() == 0, timeout=1000)
    assert "Type a query" in widget.preview_pane.toPlainText()
