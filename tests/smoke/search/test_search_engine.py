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

"""Smoke tests for search engine ranking behavior."""

from __future__ import annotations

from app.search.search_engine import search_snapshot


def test_search_snapshot_returns_symbol_and_file_hits():
    file_corpus = {"app/sample.py": "def add(a, b):\n    return a + b\n"}
    symbols = [
        {
            "name": "add",
            "qualified_name": "add",
            "kind": "function",
            "line": 1,
            "path": "app/sample.py",
            "signature": "add(a, b)",
        }
    ]

    results = search_snapshot(file_corpus=file_corpus, symbols=symbols, excel_rows=[], query="add", scope="all", limit=10)
    assert results
    result_types = {item["type"] for item in results}
    assert "file" in result_types
    assert "symbol" in result_types


def test_search_snapshot_includes_file_type_field():
    file_corpus = {"src/sample.py": "needle"}
    symbols = [
        {
            "name": "needle_sum",
            "qualified_name": "needle_sum",
            "signature": "needle_sum(a, b)",
            "path": "src/util.c",
            "line": 4,
        }
    ]
    excel_rows = [{"file": "data/inventory.csv", "row": 2, "field": "name", "value": "needle item"}]

    results = search_snapshot(
        file_corpus=file_corpus,
        symbols=symbols,
        excel_rows=excel_rows,
        query="needle",
        scope="all",
        limit=20,
    )

    by_type = {item["type"]: item for item in results}
    assert by_type["file"]["file_type"] == "py"
    assert by_type["symbol"]["file_type"] == "c"
    assert by_type["excel"]["file_type"] == "csv"
