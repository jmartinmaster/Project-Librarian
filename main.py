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

"""Application entrypoint for standalone Project Librarian."""

from __future__ import annotations

import sys
import ctypes
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

from app import APP_NAME, STARTUP_INDEX_NOTE
from app.config import AppConfig, load_config
from app.indexer.index_manager import IndexManager
from app.ui.main_window import MainWindow


def _build_splash_pixmap(icon: QIcon | None) -> QPixmap:
    """Create a lightweight branded splash image without extra asset files."""
    pixmap = QPixmap(520, 280)
    pixmap.fill(QColor("#f6f0df"))

    painter = QPainter(pixmap)
    painter.fillRect(0, 0, 520, 280, QColor("#f6f0df"))
    painter.fillRect(0, 0, 520, 12, QColor("#3c4a3f"))
    painter.fillRect(0, 268, 520, 12, QColor("#a56a3a"))

    if icon is not None and not icon.isNull():
        icon.paint(painter, 28, 44, 84, 84)

    painter.setPen(QColor("#1f2521"))
    title_font = QFont("Georgia", 22)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(132, 92, APP_NAME)

    subtitle_font = QFont("Segoe UI", 10)
    painter.setFont(subtitle_font)
    painter.setPen(QColor("#3b3027"))
    painter.drawText(132, 122, "Indexing local code and spreadsheet libraries")

    note_font = QFont("Segoe UI", 9)
    painter.setFont(note_font)
    painter.setPen(QColor("#50483f"))
    painter.drawText(28, 190, 464, 40, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, STARTUP_INDEX_NOTE)
    painter.end()
    return pixmap


def _show_startup_splash(app: QApplication, config: AppConfig, icon: QIcon | None) -> QSplashScreen:
    """Show a startup splash screen with launch-folder indexing guidance."""
    splash = QSplashScreen(_build_splash_pixmap(icon))
    launch_note = STARTUP_INDEX_NOTE if not config.project_root else f"Index root: {config.project_root}"
    splash.showMessage(
        f"Starting Project Librarian...\n{launch_note}",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#2f261f"),
    )
    splash.show()
    app.processEvents()
    return splash


def main() -> int:
    """Launch the desktop application."""
    config = load_config()
    if not config.project_root:
        config.project_root = str(Path.cwd())

    if sys.platform == "win32":
        # Ensure Windows taskbar groups this process under the app identity, not python.exe.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ProjectLibrarian.Desktop")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("project-librarian")
    icon_path = Path(__file__).resolve().parent / "app" / "ui" / "assets" / "library_icon.svg"
    app_icon: QIcon | None = None
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    splash = _show_startup_splash(app, config, app_icon)

    manager = IndexManager(config=config)
    splash.showMessage("Refreshing in-memory index...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, QColor("#2f261f"))
    app.processEvents()
    manager.refresh()
    app.aboutToQuit.connect(manager.stop_refresh_worker)

    window = MainWindow(index_manager=manager)
    manager.start_refresh_worker()
    window.show()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
