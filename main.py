"""Application entrypoint for standalone Project Librarian."""

from __future__ import annotations

import sys
import ctypes
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.config import load_config
from app.indexer.index_manager import IndexManager
from app.ui.main_window import MainWindow


def main() -> int:
    """Launch the desktop application."""
    config = load_config()
    if not config.project_root:
        config.project_root = str(Path.cwd())

    manager = IndexManager(config=config)
    manager.refresh()

    if sys.platform == "win32":
        # Ensure Windows taskbar groups this process under the app identity, not python.exe.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ProjectLibrarian.Desktop")

    app = QApplication(sys.argv)
    app.setApplicationName("Project Librarian")
    app.setApplicationDisplayName("Project Librarian")
    app.setDesktopFileName("project-librarian")
    icon_path = Path(__file__).resolve().parent / "app" / "ui" / "assets" / "library_icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.aboutToQuit.connect(manager.stop_refresh_worker)

    window = MainWindow(index_manager=manager)
    manager.start_refresh_worker()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
