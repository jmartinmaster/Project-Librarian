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
"""Notes manager for creating, indexing, and organizing project edit notes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class NotesManager:
    """Manages project edit notes saved in '<project_root>/The_Librarian/note(hour, minute, month, day, year).librarian'."""

    NOTES_DIR_NAME = "The_Librarian"
    FILE_EXTENSION = ".librarian"

    @classmethod
    def get_notes_dir(cls, repo_root: str | Path) -> Path:
        """Get or create the dedicated notes directory."""
        directory = Path(repo_root) / cls.NOTES_DIR_NAME
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @classmethod
    def generate_note_filename(cls, dt: datetime | None = None) -> str:
        """
        Generate note filename in exact specified format:
        note(hour, minute, month, day, year).librarian
        """
        now = dt or datetime.now()
        # Format: note(HH,MM,MM,DD,YYYY).librarian
        return now.strftime("note(%H,%M,%m,%d,%Y).librarian")

    @classmethod
    def list_notes(cls, repo_root: str | Path) -> list[dict[str, Any]]:
        """
        Index and load all notes stored in The_Librarian/.
        Sorted by timestamp descending (newest first).
        """
        notes_dir = cls.get_notes_dir(repo_root)
        results: list[dict[str, Any]] = []

        for file_path in notes_dir.glob(f"*{cls.FILE_EXTENSION}"):
            try:
                raw_text = file_path.read_text(encoding="utf-8")
                data = json.loads(raw_text)
                if isinstance(data, dict):
                    data["_filename"] = file_path.name
                    data["_filepath"] = str(file_path.resolve())
                    data["_mtime"] = file_path.stat().st_mtime
                    results.append(data)
            except Exception:
                pass

        results.sort(key=lambda n: str(n.get("timestamp") or n.get("_mtime", "")), reverse=True)
        return results

    @classmethod
    def save_note(
        cls,
        repo_root: str | Path,
        note_data: dict[str, Any],
        filename: str | None = None,
    ) -> tuple[bool, str, str]:
        """
        Save a note to disk. If filename is not provided, generates a new timestamped filename.
        """
        notes_dir = cls.get_notes_dir(repo_root)
        now = datetime.now()

        if not filename:
            filename = cls.generate_note_filename(now)
            # Ensure unique filename if created within the same minute
            counter = 1
            base_stem = filename[:-len(cls.FILE_EXTENSION)]
            while (notes_dir / filename).exists():
                filename = f"{base_stem}_{counter}{cls.FILE_EXTENSION}"
                counter += 1

        target_file = notes_dir / filename
        payload = dict(note_data)
        if "timestamp" not in payload:
            payload["timestamp"] = now.isoformat()
        payload["updated_at"] = now.isoformat()

        # Clean metadata fields before saving
        payload.pop("_filename", None)
        payload.pop("_filepath", None)
        payload.pop("_mtime", None)

        try:
            target_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return True, f"Saved note: {filename}", filename
        except Exception as exc:
            return False, f"Failed to save note: {exc}", filename

    @classmethod
    def delete_note(cls, repo_root: str | Path, filename: str) -> tuple[bool, str]:
        """Delete a note file."""
        notes_dir = cls.get_notes_dir(repo_root)
        target_file = notes_dir / filename
        if not target_file.exists():
            return False, f"Note file not found: {filename}"
        try:
            target_file.unlink()
            return True, f"Deleted note: {filename}"
        except Exception as exc:
            return False, f"Failed to delete note: {exc}"
