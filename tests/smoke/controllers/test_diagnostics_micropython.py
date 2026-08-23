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
"""Smoke tests for DiagnosticsController MicroPython handling."""

from __future__ import annotations

from app.controllers.diagnostics_controller import DiagnosticsController


def test_diagnostics_recognizes_micropython_modules():
    assert DiagnosticsController.is_micropython_import("machine") is True
    assert DiagnosticsController.is_micropython_import("rp2") is True
    assert DiagnosticsController.is_micropython_import("utime") is True
    assert DiagnosticsController.is_micropython_import("requests") is False


def test_diagnostics_suggested_package_for_micropython():
    suggestion_machine = DiagnosticsController.suggested_package_name("machine")
    assert "micropython-stubs" in suggestion_machine
    assert "MicroPython Built-in" in suggestion_machine

    suggestion_cv2 = DiagnosticsController.suggested_package_name("cv2")
    assert suggestion_cv2 == "opencv-python"

    suggestion_unknown = DiagnosticsController.suggested_package_name("unknown_lib")
    assert suggestion_unknown == "unknown_lib"
