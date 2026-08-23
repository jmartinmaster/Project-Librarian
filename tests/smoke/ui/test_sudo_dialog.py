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
"""Smoke tests for SudoAuthDialog and PythonHighlighter styling."""

from __future__ import annotations

from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QLineEdit

from app.views.mvc_sync.editor import PythonHighlighter
from app.views.sudo_dialog import SudoAuthDialog


def test_sudo_dialog_initialization(qtbot):
    dialog = SudoAuthDialog(port="/dev/ttyACM0", error_detail="Permission denied")
    qtbot.addWidget(dialog)

    assert dialog.port == "/dev/ttyACM0"
    assert dialog.should_fix_port_permissions() is True
    assert dialog.password_edit.echoMode() == QLineEdit.EchoMode.Password

    # Test show password toggle
    dialog.show_pass_check.setChecked(True)
    assert dialog.password_edit.echoMode() == QLineEdit.EchoMode.Normal

    dialog.password_edit.setText("mysecret")
    assert dialog.get_password() == "mysecret"


def test_python_highlighter_micropython_mode(qtbot):
    doc = QTextDocument()
    doc.setPlainText("import machine\nfrom micropython import const\n# Normal comment\n'''Docstring'''\n")
    highlighter = PythonHighlighter(doc, micropython_mode=False)

    assert highlighter.micropython_mode is False
    highlighter.set_micropython_mode(True)
    assert highlighter.micropython_mode is True
