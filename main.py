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
import os
import subprocess
import threading

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSplashScreen,
    QVBoxLayout,
)

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


class RebuildThread(QThread):
    """Worker thread to run background index rebuild."""
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, manager: IndexManager) -> None:
        super().__init__()
        self.manager = manager

    def run(self) -> None:
        try:
            self.manager.refresh()
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


def _show_rebuild_dialog(app: QApplication, manager: IndexManager) -> None:
    """Show a non-modal QDialog with a progress bar while indexing completes."""
    dialog = QDialog()
    dialog.setWindowTitle("Building Index")
    dialog.setMinimumWidth(400)
    dialog.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

    layout = QVBoxLayout(dialog)
    label = QLabel(
        "First-time startup: Building Project Librarian search indexes and snapshot.\n"
        "This may take a moment...",
        dialog
    )
    layout.addWidget(label)

    progress = QProgressBar(dialog)
    progress.setRange(0, 0) # Indeterminate progress bar (marquee)
    layout.addWidget(progress)

    thread = RebuildThread(manager)

    def on_finished():
        dialog.accept()

    def on_error(err_msg):
        dialog.reject()
        QMessageBox.critical(None, "Indexing Error", f"Failed to build search index: {err_msg}")
        sys.exit(1)

    thread.finished_signal.connect(on_finished)
    thread.error_signal.connect(on_error)

    thread.start()
    dialog.exec()


def main() -> int:
    """Launch the desktop application."""
    if "--test-crash" in sys.argv:
        print("Intentional test crash triggered!", file=sys.stderr)
        raise RuntimeError("Test crash traceback output")

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

    # Check if snapshot exists. If not, build it before launching MainWindow.
    repo_root = Path(config.project_root or Path.cwd()).resolve()
    output_candidate = Path(config.output_dir)
    output_dir = output_candidate if output_candidate.is_absolute() else repo_root / output_candidate
    snapshot_path = output_dir / "librarian-snapshot.json"
    if not snapshot_path.exists():
        splash.hide()
        _show_rebuild_dialog(app, manager)
        splash.show()

    splash.showMessage(
        "Launching UI and starting background indexing...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#2f261f"),
    )
    app.processEvents()
    app.aboutToQuit.connect(manager.stop_refresh_worker)

    window = MainWindow(index_manager=manager)
    window.show()
    splash.finish(window)
    manager.start_refresh_worker(run_immediately=True)
    return app.exec()


def show_crash_dialog(exit_code: int, traceback_str: str) -> bool:
    """Show a crash dialog using PyQt6.
    
    If PyQt6 fails, falls back to a basic OS messagebox or console logging.
    Returns True if the user selected 'Restart Application'.
    """
    restart_requested = [False]
    try:
        from PyQt6.QtWidgets import (
            QApplication,
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QTextEdit,
            QPushButton,
            QStyle,
        )
        from PyQt6.QtGui import QFont, QIcon
        from PyQt6.QtCore import Qt
        
        app = QApplication.instance()
        if not app:
            app = QApplication([])
            app.setApplicationName("Project Librarian Supervisor")
            icon_path = Path(__file__).resolve().parent / "app" / "ui" / "assets" / "library_icon.svg"
            if icon_path.exists():
                app.setWindowIcon(QIcon(str(icon_path)))
                
        dialog = QDialog()
        dialog.setWindowTitle("Application Crash Detected")
        dialog.setMinimumSize(650, 450)
        # Keep dialog on top
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(dialog)
        
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        error_icon = dialog.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        icon_label.setPixmap(error_icon.pixmap(48, 48))
        header_layout.addWidget(icon_label)
        
        title_text = (
            "<h3>Project Librarian Crashed</h3>"
            "<p>The application encountered a fatal error and had to close.</p>"
        )
        title_label = QLabel(title_text)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        info_label = QLabel(f"<b>Exit Code:</b> {exit_code}<br/><b>Error Traceback:</b>")
        layout.addWidget(info_label)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 9))
        text_edit.setPlainText(traceback_str or "No error output captured in stderr.")
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        
        restart_btn = QPushButton("Restart Application")
        restart_btn.setDefault(True)
        def on_restart():
            restart_requested[0] = True
            dialog.accept()
            
        restart_btn.clicked.connect(on_restart)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(restart_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    except Exception as e:
        print(f"\n[Supervisor] Child process crashed with exit code {exit_code}.", file=sys.stderr)
        print(f"[Supervisor] Fallback crash logger error: {e}", file=sys.stderr)
        print(f"[Supervisor] Child Traceback:\n{traceback_str}", file=sys.stderr)
        
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Project Librarian has crashed.\n\nExit Code: {exit_code}\n\nTraceback summary:\n{traceback_str[:500]}",
                "Application Crash Detected",
                0x10 | 0x0  # MB_ICONERROR | MB_OK
            )
            
    return restart_requested[0]


def supervisor_main() -> int:
    """Launch the supervisor process to monitor the child process."""
    while True:
        env = os.environ.copy()
        env["PROJECT_LIBRARIAN_IS_CHILD"] = "1"
        
        if getattr(sys, "frozen", False):
            # Compiled executable (PyInstaller)
            cmd = [sys.executable] + sys.argv[1:]
        else:
            # Script run
            cmd = [sys.executable, sys.argv[0]] + sys.argv[1:]
            
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
            
        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=None,  # Live stream stdout to parent's stdout
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except Exception as e:
            print(f"Failed to start child process: {e}", file=sys.stderr)
            show_crash_dialog(-1, f"Failed to start child process: {e}")
            return 1
            
        stderr_lines = []
        def read_stderr():
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                sys.stderr.write(line)
                sys.stderr.flush()
                stderr_lines.append(line)
                if len(stderr_lines) > 200:
                    stderr_lines.pop(0)
                    
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        
        exit_code = process.wait()
        stderr_thread.join(timeout=2.0)
        
        if exit_code == 0:
            return 0
            
        crash_log = "".join(stderr_lines)
        should_restart = show_crash_dialog(exit_code, crash_log)
        if not should_restart:
            return exit_code


if __name__ == "__main__":
    bypass_supervisor = False
    if "--no-supervisor" in sys.argv:
        bypass_supervisor = True
        sys.argv.remove("--no-supervisor")
    elif os.environ.get("PROJECT_LIBRARIAN_NO_SUPERVISOR") == "1":
        bypass_supervisor = True
        
    if bypass_supervisor or os.environ.get("PROJECT_LIBRARIAN_IS_CHILD") == "1":
        # Restore sys.stdout and sys.stderr from file descriptors 1 and 2 if PyInstaller set them to None
        import io
        for fd, stream_name in ((1, "stdout"), (2, "stderr")):
            stream = getattr(sys, stream_name)
            if stream is None or not hasattr(stream, "write"):
                try:
                    setattr(sys, stream_name, io.TextIOWrapper(open(fd, "wb"), encoding="utf-8", write_through=True))
                except Exception:
                    pass
            else:
                try:
                    if hasattr(stream, "buffer"):
                        setattr(sys, stream_name, io.TextIOWrapper(stream.buffer, encoding="utf-8", write_through=True))
                except Exception:
                    pass

        # Intercept PyQt6/Python unhandled exceptions and write them to stderr cleanly
        def custom_excepthook(exc_type, exc_value, exc_traceback):
            import traceback as tb
            print("Unhandled exception caught in main thread excepthook:", file=sys.stderr)
            tb.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
            if sys.stderr:
                sys.stderr.flush()
            sys.exit(1)

        def custom_thread_excepthook(args):
            import traceback as tb
            print(f"Unhandled exception caught in thread {args.thread.name if args.thread else 'unknown'}:", file=sys.stderr)
            tb.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr)
            if sys.stderr:
                sys.stderr.flush()
            # Force the entire process to exit rather than just the thread
            os._exit(1)

        sys.excepthook = custom_excepthook
        threading.excepthook = custom_thread_excepthook

        try:
            import faulthandler
            faulthandler.enable()
        except Exception:
            pass
        raise SystemExit(main())
    else:
        raise SystemExit(supervisor_main())
