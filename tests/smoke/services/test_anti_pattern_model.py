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

import pytest
import re
from app.models.anti_pattern_model import DEFAULT_ANTI_PATTERNS

def test_anti_pattern_regex_eval_exec():
    eval_exec_preset = next(p for p in DEFAULT_ANTI_PATTERNS if p["name"] == "Eval / Exec Usage")
    pattern = re.compile(eval_exec_preset["regex"])
    
    assert pattern.search("eval('1 + 1')") is not None
    assert pattern.search("exec(code_str)") is not None
    assert pattern.search("  eval(something)") is not None
    
    assert pattern.search("dialog.exec()") is None
    assert pattern.search("app.exec()") is None
    assert pattern.search("menu.exec(pos)") is None
    assert pattern.search("selected = menu.exec(position)") is None
    assert pattern.search("description = 'Using eval or exec'") is None

def test_anti_pattern_bare_except_description():
    bare_except_preset = next(p for p in DEFAULT_ANTI_PATTERNS if p["name"] == "Bare Except")
    assert "except:" not in bare_except_preset["description"]
