# app/views/about.py - About Dialog for MVC Sync Editor
# Copyright (C) 2026 Jamie Martin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QTextEdit, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices

class AboutDialog(QDialog):
    """
    A custom styled dark-mode 'About' Dialog.
    Contains information about MVC Sync Editor, GNU GPL v3 license details,
    and a specific warning/notice regarding the copyleft PyQt6 license requirements.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MVC Sync Editor")
        self.resize(550, 480)
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        # Set stylesheet matching the premium Catppuccin Mocha theme of MVC Editor
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 12px;
            }
            QTextEdit {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                font-size: 11px;
                line-height: 140%;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:pressed {
                background-color: #74c7ec;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                background-color: #1e1e2e;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #11111b;
                color: #a6adc8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:hover {
                background-color: #313244;
            }
            QTabBar::tab:selected {
                background-color: #1e1e2e;
                color: #f5c2e7;
                border-bottom: 2px solid #f5c2e7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Header Widget
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        app_title = QLabel("MVC Sync Editor")
        app_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f5c2e7;")
        header_layout.addWidget(app_title)

        app_version = QLabel("Version 1.0.0")
        app_version.setStyleSheet("font-size: 11px; font-weight: 600; color: #a6adc8;")
        header_layout.addWidget(app_version)

        app_desc = QLabel("A high-fidelity dark-mode IDE for MVC-patterned PyQt6 applications.")
        app_desc.setStyleSheet("font-size: 12px; color: #cdd6f4; font-style: italic;")
        header_layout.addWidget(app_desc)

        layout.addWidget(header_widget)

        # Separator line
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #313244;")
        layout.addWidget(sep)

        # 2. Tab Widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab A: About/Details
        tab_about = QWidget()
        tab_about_layout = QVBoxLayout(tab_about)
        tab_about_layout.setContentsMargins(10, 10, 10, 10)
        tab_about_layout.setSpacing(10)

        about_text = QLabel(
            "<b>MVC Sync Editor</b> is structured with the classic Model-View-Controller "
            "(MVC) architectural pattern. It features multi-pane file synchronization, "
            "automated AST code analysis to detect method calls, signal connections, and "
            "property updates across Python files, and an integrated subprocess console.<br><br>"
            "<b>Developer:</b> Jamie Martin<br>"
            "<b>Framework:</b> PyQt6 (Qt 6.4.0+)<br>"
            "<b>Python Version:</b> 3.8+"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("line-height: 130%; color: #cdd6f4;")
        tab_about_layout.addWidget(about_text)
        tab_about_layout.addStretch()

        # License File Link Row
        license_row = QHBoxLayout()
        license_lbl = QLabel("To view the full license terms of this program:")
        license_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        license_lbl.setWordWrap(True)
        license_row.addWidget(license_lbl)

        view_license_btn = QPushButton("View LICENSE")
        view_license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_license_btn.clicked.connect(self.view_local_license)
        license_row.addWidget(view_license_btn)
        tab_about_layout.addLayout(license_row)

        # Qt Info Row
        qt_row = QHBoxLayout()
        qt_lbl = QLabel("To view licensing and information about the underlying Qt Framework:")
        qt_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        qt_lbl.setWordWrap(True)
        qt_row.addWidget(qt_lbl)

        about_qt_btn = QPushButton("About Qt")
        about_qt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        about_qt_btn.clicked.connect(self.show_about_qt)
        qt_row.addWidget(about_qt_btn)
        tab_about_layout.addLayout(qt_row)

        tabs.addTab(tab_about, "General")

        # Tab B: GPL License
        tab_gpl = QWidget()
        tab_gpl_layout = QVBoxLayout(tab_gpl)
        tab_gpl_layout.setContentsMargins(10, 10, 10, 10)

        gpl_text = QTextEdit()
        gpl_text.setReadOnly(True)
        gpl_text.setPlainText(
            "This program is free software: you can redistribute it and/or modify "
            "it under the terms of the GNU General Public License as published by "
            "the Free Software Foundation, either version 3 of the License, or "
            "(at your option) any later version.\n\n"
            "This program is distributed in the hope that it will be useful, "
            "but WITHOUT ANY WARRANTY; without even the implied warranty of "
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the "
            "GNU General Public License for more details.\n\n"
            "You should have received a copy of the GNU General Public License "
            "along with this program.  If not, see <https://www.gnu.org/licenses/>."
        )
        tab_gpl_layout.addWidget(gpl_text)
        tabs.addTab(tab_gpl, "GNU GPL v3")

        # Tab C: PyQt6 Notice
        tab_pyqt = QWidget()
        tab_pyqt_layout = QVBoxLayout(tab_pyqt)
        tab_pyqt_layout.setContentsMargins(10, 10, 10, 10)

        pyqt_text = QTextEdit()
        pyqt_text.setReadOnly(True)
        pyqt_text.setPlainText(
            "PyQt6 Copyright and License Notice:\n\n"
            "This application uses PyQt6 (the Python bindings for Qt 6), "
            "developed and copyright © Riverbank Computing Limited. "
            "PyQt6 is licensed under the GNU General Public License (GPL) version 3.\n\n"
            "By importing and linking with PyQt6, this application is subject "
            "to the copyleft requirements of the GPL v3 license. Therefore, the "
            "entire source code of this MVC Sync Editor is open-source and "
            "licensed under the GNU General Public License v3.\n\n"
            "If you wish to use PyQt6 or distribute applications incorporating it "
            "without being bound by the GPL, you must purchase a commercial "
            "license from Riverbank Computing Limited.\n\n"
            "Qt is a registered trademark of The Qt Company Ltd."
        )
        tab_pyqt_layout.addWidget(pyqt_text)
        tabs.addTab(tab_pyqt, "PyQt6 License Notice")

        # 3. Bottom Close Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def show_about_qt(self):
        QMessageBox.aboutQt(self, "About Qt")

    def view_local_license(self):
        import os
        license_path = os.path.abspath("LICENSE")
        if os.path.exists(license_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(license_path))
        else:
            QMessageBox.warning(self, "License File Not Found", f"The LICENSE file could not be found at:\n{license_path}")
