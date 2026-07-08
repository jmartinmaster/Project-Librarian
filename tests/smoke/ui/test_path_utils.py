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

"""Smoke tests for UI path helper behavior."""

from __future__ import annotations

from pathlib import Path

from app.ui.path_utils import absolute_containing_folder


def test_absolute_containing_folder_resolves_relative_file_path(tmp_path: Path):
    project_root = tmp_path / "repo"
    nested_file = project_root / "src" / "module.py"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("print('ok')\n", encoding="utf-8")

    folder = absolute_containing_folder("src/module.py", project_root)
    assert Path(folder) == nested_file.parent.resolve()


def test_absolute_containing_folder_keeps_absolute_folder(tmp_path: Path):
    absolute_folder = (tmp_path / "data").resolve()
    absolute_folder.mkdir(parents=True)

    folder = absolute_containing_folder(str(absolute_folder), tmp_path)
    assert Path(folder) == absolute_folder
