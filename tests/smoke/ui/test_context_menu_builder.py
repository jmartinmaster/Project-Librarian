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
"""Smoke tests for centralized ContextMenuBuilder."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from app.views.context_menu_builder import ContextMenuBuilder, ItemContext, ContextMenuCallbacks


def test_context_menu_builder_creates_standard_actions(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)

    opened_files = []
    created_notes = []
    traced_symbols = []

    callbacks = ContextMenuCallbacks(
        open_file=lambda p, l: opened_files.append((p, l)),
        create_note=lambda p, l, s, src, t, snip: created_notes.append((p, l, s, src, t, snip)),
        trace_symbol=lambda s: traced_symbols.append(s),
    )

    ctx = ItemContext(
        path="app/views/search_view.py",
        line=42,
        symbol="SearchView",
        source="Search Browser",
        title="Edit SearchView",
        snippet="class SearchView(QWidget):",
        extra_actions=[
            ("Custom Action", lambda: opened_files.append(("custom", 0)))
        ],
    )

    menu = ContextMenuBuilder.build_menu(parent, ctx, callbacks)
    action_texts = [a.text() for a in menu.actions() if a.text()]

    assert "Open in Editor" in action_texts
    assert "Open Externally" in action_texts
    assert "Trace 'SearchView' Call Hierarchy" in action_texts
    assert "📝 New Note for Item" in action_texts
    assert "Copy Path" in action_texts
    assert "Copy Reference Location" in action_texts
    assert "Custom Action" in action_texts

    # Trigger Note Action
    note_act = next(a for a in menu.actions() if "New Note" in a.text())
    note_act.trigger()
    assert len(created_notes) == 1
    assert created_notes[0][0] == "app/views/search_view.py"
    assert created_notes[0][1] == 42
    assert created_notes[0][2] == "SearchView"
    assert created_notes[0][3] == "Search Browser"

    # Trigger Custom Extra Action
    custom_act = next(a for a in menu.actions() if a.text() == "Custom Action")
    custom_act.trigger()
    assert len(opened_files) == 1
    assert opened_files[0] == ("custom", 0)
