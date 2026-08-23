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
"""Smoke tests for NotesView."""

from __future__ import annotations

from pathlib import Path
from app.views.notes_view import NotesView


def test_notes_view_create_filter_and_jump(qtbot, tmp_path: Path):
    view = NotesView(project_root=tmp_path)
    qtbot.addWidget(view)

    # 1. Create note from context
    view.create_note_from_context(
        target_file="app/views/search_view.py",
        line=42,
        symbol="SearchView",
        source="Search Browser",
        title="Enhance search filters",
        content="Add regex matching toggle",
        tags=["ui", "feature"],
    )

    assert view.title_edit.text() == "Enhance search filters"
    assert view.target_file_edit.text() == "app/views/search_view.py"
    assert view.target_line_spin.value() == 42
    assert view.source_label.text() == "Search Browser"

    # Save note
    ok = view.save_current_note()
    assert ok is True
    assert view.notes_list.count() == 1

    # 2. Test Jump signal
    jumps = []
    view.jump_requested.connect(lambda f, l: jumps.append((f, l)))
    view._jump_to_target()
    assert len(jumps) == 1
    assert jumps[0] == ("app/views/search_view.py", 42)

    # 3. Filter notes
    view.search_input.setText("Enhance")
    assert view.notes_list.count() == 1

    view.search_input.setText("non_existent_term_xyz")
    assert view.notes_list.count() == 0

    view.search_input.clear()
    assert view.notes_list.count() == 1
