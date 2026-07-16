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
"""Smoke tests for search engine regex and case-sensitive matching."""

from __future__ import annotations

from app.search.search_engine import search_snapshot


def test_search_snapshot_case_sensitive():
    file_corpus = {
        "app/module.py": "def test_func():\n    myVariable = 42\n",
        "app/other.py": "def test_func():\n    myvariable = 24\n",
    }
    symbols = []
    excel_rows = []

    # Case-insensitive (default) - should find both
    res = search_snapshot(file_corpus, symbols, excel_rows, "myVariable", match_case=False)
    assert len(res) == 2

    # Case-sensitive - should find only module.py
    res_cs = search_snapshot(file_corpus, symbols, excel_rows, "myVariable", match_case=True)
    assert len(res_cs) == 1
    assert res_cs[0]["path"] == "app/module.py"


def test_search_snapshot_regex():
    file_corpus = {
        "app/module.py": "myVariable = 42\nmyOtherVar = 100\n",
    }
    symbols = []
    excel_rows = []

    # Match digits in regex
    res = search_snapshot(file_corpus, symbols, excel_rows, r"my\w+Var", use_regex=True)
    assert len(res) == 1
    assert "myOtherVar" in res[0]["preview"]

    # Fails compiling, falls back to literal search
    res_err = search_snapshot(file_corpus, symbols, excel_rows, r"nonexistent(query", use_regex=True)
    assert len(res_err) == 0
