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
"""Path helpers shared across UI/controller clipboard workflows."""

from __future__ import annotations

from pathlib import Path


def absolute_containing_folder(path_text: str, project_root: str | Path) -> str:
    """Return absolute containing-folder path for a file-oriented path string."""
    if not path_text.strip():
        return ""
    candidate = Path(path_text.strip())
    if not candidate.is_absolute():
        candidate = (Path(project_root).resolve() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    folder = candidate if candidate.is_dir() else candidate.parent
    return str(folder)

