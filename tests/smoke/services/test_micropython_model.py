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
"""Smoke tests for MicroPython module registry and helper utilities."""

from __future__ import annotations

from app.models.micropython_model import (
    MICROPYTHON_BUILTIN_MODULES,
    MICROPYTHON_DECORATORS,
    get_micropython_module_info,
    is_micropython_decorator,
    is_micropython_module,
)


def test_micropython_builtin_modules_recognized():
    assert is_micropython_module("machine")
    assert is_micropython_module("machine.Pin")
    assert is_micropython_module("micropython")
    assert is_micropython_module("rp2")
    assert is_micropython_module("esp32")
    assert is_micropython_module("pyb")
    assert is_micropython_module("utime")
    assert is_micropython_module("uos")
    assert is_micropython_module("uasyncio")
    assert is_micropython_module("uctypes")
    assert is_micropython_module("neopixel")


def test_standard_non_micropython_modules():
    assert not is_micropython_module("numpy")
    assert not is_micropython_module("pandas")
    assert not is_micropython_module("flask")
    assert not is_micropython_module("")


def test_get_micropython_module_info():
    info = get_micropython_module_info("machine")
    assert info is not None
    assert "hardware" in info["category"]

    info_none = get_micropython_module_info("nonexistent_xyz")
    assert info_none is None


def test_micropython_decorators_recognized():
    assert is_micropython_decorator("micropython.native")
    assert is_micropython_decorator("@micropython.native")
    assert is_micropython_decorator("micropython.viper")
    assert is_micropython_decorator("@micropython.asm_thumb")
    assert is_micropython_decorator("native")
    assert is_micropython_decorator("viper")
    assert not is_micropython_decorator("property")
    assert not is_micropython_decorator("classmethod")
