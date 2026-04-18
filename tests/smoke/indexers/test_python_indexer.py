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

"""Smoke tests for Python symbol indexing."""

from __future__ import annotations

from app.indexer.python_indexer import index_python_symbols


def test_index_python_symbols_finds_class_and_function(sample_repo):
    symbols = index_python_symbols(sample_repo)
    names = {item["qualified_name"] for item in symbols}
    assert "Example" in names
    assert "Example.ping" in names
    assert "add" in names
