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
"""Integrated Sudo authentication and permission elevation dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class SudoAuthDialog(QDialog):
    """Modal dialog prompting user for password to elevate device permissions."""

    def __init__(
        self,
        port: str = "auto",
        error_detail: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.port = port
        self.error_detail = error_detail

        self.setWindowTitle("Root / Sudo Elevation Required")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                color: #cdd6f4;
            }
            QLineEdit {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QRadioButton {
                color: #cdd6f4;
            }
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header_label = QLabel("<b>Device Access Denied: Permission Elevation Required</b>", self)
        header_label.setStyleSheet("font-size: 13px; color: #f38ba8;")
        layout.addWidget(header_label)

        desc_text = (
            f"The system reported a permission error while accessing microcontroller port <code>{self.port}</code>.<br>"
            "To grant access, please select a remediation option and enter your sudo password:"
        )
        desc_label = QLabel(desc_text, self)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Radio options
        self.fix_port_radio = QRadioButton(f"Fix port permissions: sudo chmod 666 {self.port} (Recommended)", self)
        self.fix_port_radio.setChecked(True)
        layout.addWidget(self.fix_port_radio)

        self.run_sudo_radio = QRadioButton("Execute runner command as sudo", self)
        layout.addWidget(self.run_sudo_radio)

        form = QFormLayout()
        self.password_edit = QLineEdit(self)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Enter sudo password")
        form.addRow("Sudo Password:", self.password_edit)
        layout.addLayout(form)

        show_pass_row = QHBoxLayout()
        self.show_pass_check = QCheckBox("Show password", self)
        self.show_pass_check.toggled.connect(self._toggle_show_password)
        show_pass_row.addWidget(self.show_pass_check)
        show_pass_row.addStretch(1)
        layout.addLayout(show_pass_row)

        if self.error_detail:
            err_box = QLabel(f"<small><i>{self.error_detail[:120]}...</i></small>", self)
            err_box.setStyleSheet("color: #a6adc8;")
            layout.addWidget(err_box)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _toggle_show_password(self, checked: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def get_password(self) -> str:
        """Return entered password."""
        return self.password_edit.text()

    def should_fix_port_permissions(self) -> bool:
        """Return True if user selected to fix port permissions."""
        return self.fix_port_radio.isChecked()
