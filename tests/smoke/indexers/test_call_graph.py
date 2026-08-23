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
"""Smoke tests for CallGraphEngine."""

from __future__ import annotations

from pathlib import Path
from app.indexer.call_graph import CallGraphEngine


def test_call_graph_engine_identifies_callers_and_callees(tmp_path: Path):
    math_file = tmp_path / "math_utils.py"
    math_file.write_text("""
def add(a, b):
    return a + b

def calculate_total(items):
    total = 0
    for it in items:
        total = add(total, it)
    return total
""", encoding="utf-8")

    caller_file = tmp_path / "main.py"
    caller_file.write_text("""
from math_utils import calculate_total

def run():
    res = calculate_total([1, 2, 3])
    print(res)
""", encoding="utf-8")

    symbols = [
        {"name": "add", "qualified_name": "add", "kind": "function", "line": 2, "end_line": 3, "path": "math_utils.py"},
        {"name": "calculate_total", "qualified_name": "calculate_total", "kind": "function", "line": 5, "end_line": 9, "path": "math_utils.py"},
        {"name": "run", "qualified_name": "run", "kind": "function", "line": 4, "end_line": 6, "path": "main.py"},
    ]

    graph = CallGraphEngine.analyze_symbol(tmp_path, "calculate_total", symbols=symbols)
    assert graph["symbol"] == "calculate_total"
    assert graph["definition"] is not None
    assert graph["definition"]["path"] == "math_utils.py"

    # Check caller detected in main.py
    callers = [c for c in graph["callers"] if c["file"] == "main.py"]
    assert len(callers) >= 1
    assert any("calculate_total" in c["snippet"] for c in callers)

    # Check callee 'add' detected in math_utils.py
    callees = [c for c in graph["callees"] if c["name"] == "add"]
    assert len(callees) == 1
