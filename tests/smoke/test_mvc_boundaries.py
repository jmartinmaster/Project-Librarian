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
"""Smoke assertions for MVC boundary expectations."""

from __future__ import annotations

from pathlib import Path


def test_non_view_layers_have_no_pyqt_imports() -> None:
    """Keep PyQt imports restricted to app/views only."""
    repo_root = Path(__file__).resolve().parents[2]
    scan_paths = [
        repo_root / "app" / "controllers",
        repo_root / "app" / "services",
        repo_root / "app" / "indexer",
        repo_root / "app" / "search",
        repo_root / "app" / "config.py",
    ]
    markers = ("from PyQt6", "import PyQt6")

    violations: list[str] = []
    for scan_path in scan_paths:
        if scan_path.is_file():
            files = [scan_path]
        else:
            files = sorted(scan_path.rglob("*.py"))
        for file_path in files:
            text = file_path.read_text(encoding="utf-8")
            if any(marker in text for marker in markers):
                violations.append(str(file_path.relative_to(repo_root)))

    assert violations == []
