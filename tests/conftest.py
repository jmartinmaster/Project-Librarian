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

"""Shared fixtures for Project Librarian smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import AppConfig


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a small sample repository tree for indexing tests."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    (app_dir / "sample.py").write_text(
        """
class Example:
    def ping(self, value):
        return value

def add(a, b):
    return a + b
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (tmp_path / "sample.c").write_text(
        """
struct person { int id; };
int sum(int a, int b) { return a + b; }
""".strip()
        + "\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def app_config(sample_repo: Path) -> AppConfig:
    """Return a baseline config targeting the sample repo."""
    return AppConfig(
        project_root=str(sample_repo),
        output_dir="build",
        excluded_dirs=[".git", ".venv", "__pycache__", "build"],
        file_extensions=[".py", ".c", ".h", ".md", ".json", ".txt"],
        refresh_interval_seconds=30,
        index_python=True,
        index_c=True,
        excel_folder="",
        excel_keyword_columns=[],
    )
