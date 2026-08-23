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
"""Smoke tests for CallGraphView."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.views.call_graph_view import CallGraphView


def test_call_graph_view_trace_and_render(qtbot, tmp_path: Path):
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

    mock_manager = MagicMock()
    mock_manager.config.project_root = str(tmp_path)
    mock_manager.state.symbols = [
        {"name": "add", "qualified_name": "add", "kind": "function", "line": 2, "end_line": 3, "path": "math_utils.py", "signature": "add(a, b)"},
        {"name": "calculate_total", "qualified_name": "calculate_total", "kind": "function", "line": 5, "end_line": 9, "path": "math_utils.py", "signature": "calculate_total(items)"},
        {"name": "run", "qualified_name": "run", "kind": "function", "line": 4, "end_line": 6, "path": "main.py", "signature": "run()"},
    ]
    mock_manager.state.file_corpus = []

    view = CallGraphView(index_manager=mock_manager)
    qtbot.addWidget(view)

    # Trace calculate_total
    view.symbol_input.setText("calculate_total")
    view.trace_symbol()

    assert "calculate_total" in view.def_title_label.text()
    assert view.callers_table.rowCount() >= 1
    assert view.callees_list.count() >= 1

    # Jump signal on caller double click
    jumps = []
    view.jump_requested.connect(lambda f, l: jumps.append((f, l)))
    view._on_caller_double_clicked(0, 0)
    assert len(jumps) == 1
    assert jumps[0][0] == "main.py"
