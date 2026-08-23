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
"""Smoke tests for NotesManager."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from app.models.notes_manager import NotesManager


def test_notes_manager_filename_format():
    dt = datetime(2026, 8, 23, 14, 5)
    filename = NotesManager.generate_note_filename(dt)
    assert filename == "note(14,05,08,23,2026).librarian"


def test_notes_manager_crud_lifecycle(tmp_path: Path):
    note_payload = {
        "title": "Refactor REPL streaming",
        "target_file": "app/models/micropython_runner.py",
        "target_line": 240,
        "target_symbol": "start_repl_monitor",
        "source_component": "Code Audit",
        "tags": ["refactor", "hardware"],
        "note_content": "Clean up buffer reading loop to avoid CPU spin.",
        "code_snippet": "while not stop_event.is_set(): ...",
    }

    # 1. Save Note
    ok, msg, filename = NotesManager.save_note(tmp_path, note_payload)
    assert ok is True
    assert filename.startswith("note(")
    assert filename.endswith(".librarian")

    # Check directory created
    notes_dir = tmp_path / "The_Librarian"
    assert notes_dir.exists()
    assert (notes_dir / filename).exists()

    # 2. List Notes
    notes = NotesManager.list_notes(tmp_path)
    assert len(notes) == 1
    assert notes[0]["title"] == "Refactor REPL streaming"
    assert notes[0]["target_file"] == "app/models/micropython_runner.py"
    assert notes[0]["_filename"] == filename

    # 3. Update Note
    note_payload["title"] = "Updated title"
    ok_up, msg_up, fn_up = NotesManager.save_note(tmp_path, note_payload, filename=filename)
    assert ok_up is True
    assert fn_up == filename

    notes_updated = NotesManager.list_notes(tmp_path)
    assert len(notes_updated) == 1
    assert notes_updated[0]["title"] == "Updated title"

    # 4. Delete Note
    ok_del, msg_del = NotesManager.delete_note(tmp_path, filename)
    assert ok_del is True
    assert not (notes_dir / filename).exists()
    assert len(NotesManager.list_notes(tmp_path)) == 0
