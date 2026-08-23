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
"""Smoke tests for indexing Python files with MicroPython decorators."""

from __future__ import annotations

from pathlib import Path

from app.indexer.python_indexer import index_python_symbols


def test_index_micropython_decorated_code(tmp_path):
    src_dir = tmp_path / "mcu_app"
    src_dir.mkdir(parents=True, exist_ok=True)

    test_file = src_dir / "driver.py"
    test_file.write_text(
        'import micropython\n'
        'import machine\n\n'
        '@micropython.native\n'
        'def compute_fast(a, b):\n'
        '    """Fast native computation."""\n'
        '    return a * b + 1\n\n'
        '@micropython.viper\n'
        'def direct_memory_access(ptr: int) -> int:\n'
        '    """Viper emitter memory read."""\n'
        '    return ptr\n\n'
        'class Sensor:\n'
        '    """Hardware sensor interface."""\n'
        '    @micropython.native\n'
        '    def read_raw(self, pin_num):\n'
        '        return pin_num\n',
        encoding="utf-8",
    )

    symbols_ast = index_python_symbols(tmp_path, use_cst=False)
    symbols_cst = index_python_symbols(tmp_path, use_cst=True)

    names_ast = {s["qualified_name"] for s in symbols_ast}
    names_cst = {s["qualified_name"] for s in symbols_cst}

    assert "compute_fast" in names_ast
    assert "direct_memory_access" in names_ast
    assert "Sensor" in names_ast
    assert "Sensor.read_raw" in names_ast

    assert names_ast == names_cst

    # Check decorator extraction
    sym_fast = next(s for s in symbols_ast if s["name"] == "compute_fast")
    assert "micropython.native" in sym_fast.get("decorators", [])

    sym_viper = next(s for s in symbols_ast if s["name"] == "direct_memory_access")
    assert "micropython.viper" in sym_viper.get("decorators", [])
