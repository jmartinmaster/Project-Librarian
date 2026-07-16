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
"""In-app Help Dialog showing the Project Librarian User Guide."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

# HTML User Guide topics matching app functionality
HELP_TOPICS = {
    "General Overview": """
        <h1>The Librarian</h1>
        <p>The Librarian is a local PyQt6 desktop application designed to index source code and spreadsheets into a fast, in-memory search library. Built with a decoupled <b>Model-View-Controller (MVC)</b> design pattern, the application separates user interface presentation, workflow orchestration, and business logic layers.</p>
        
        <h3>Key Architecture Details</h3>
        <ul>
            <li><b>Process-Level Parallelism:</b> Uses <code>ProcessPoolExecutor</code> to offload file scanning and symbol extraction to background child processes. This bypasses the Python GIL (Global Interpreter Lock), keeps the application fully responsive, and isolates indexing crashes.</li>
            <li><b>RAM-Cached Corpus:</b> Retains the full file corpus, Python/C symbol metadata, and spreadsheet rows in memory for near-instantaneous searching.</li>
            <li><b>Configuration:</b> Settings and cached data are persisted in platform-specific folders (e.g., <code>%APPDATA%</code> or <code>%LOCALAPPDATA%</code> on Windows, <code>Application Support</code> on macOS, and <code>~/.config</code> on Linux).</li>
        </ul>
    """,
    "Search & Navigation": """
        <h1>Search &amp; Navigation</h1>
        <p>The core of The Librarian is finding files, symbols, and cell content quickly.</p>
        
        <h3>Search Browser</h3>
        <p>Supports searching the entire indexed workspace. Search results show the <b>File Name</b>, <b>Type</b> (e.g., Class, Function, Row, File), and <b>File Type</b> (e.g., <code>.py</code>, <code>.c</code>, <code>.csv</code>) to quickly identify formats. Double-clicking any result opens the file directly in the embedded MVC Editor.</p>
        
        <h3>Line-Context Preview</h3>
        <p>Selecting a search result immediately displays a contextual line preview in the bottom pane, showing lines directly surrounding the matched search term.</p>
        
        <h3>Indexed Library Pane</h3>
        <p>The dockable left sidebar offers a browse-first discovery explorer. It supports:</p>
        <ul>
            <li><b>Tree/Flat View Toggle:</b> Tree view mirrors the directory structure, while Flat view lists files and symbols alphabetically.</li>
            <li><b>Live Filter Input:</b> Instantly filter files, classes, methods, or skipped files in the tree hierarchy.</li>
            <li><b>Context Menu Actions:</b> Right-click any file to copy its <b>Absolute Containing Folder Path</b> to the clipboard (excluding filename/extension to prevent accidental execution behavior).</li>
        </ul>
        
        <h3>Excel Library Browser</h3>
        <p>Search across indexed spreadsheet rows. You can configure key columns under <b>Preferences</b> to determine how rows are summarized and indexed.</p>
    """,
    "MVC Sync Editor": """
        <h1>MVC Sync Editor</h1>
        <p>The integrated code editor allows you to explore and modify code using MVC boundaries.</p>
        
        <h3>Integrated Design</h3>
        <p>Embedded as a core tab inside the main window, it removes the external window frame chrome to align with host theming and styles.</p>
        
        <h3>Triad Discovery &amp; Views</h3>
        <ul>
            <li><b>Triad Tabs:</b> The editor splits files into coordinated <b>Model</b>, <b>View</b>, and <b>Controller</b> tabs. If you open a view or controller file, the editor attempts to auto-discover and load the corresponding parts of the triad.</li>
            <li><b>Inspector Seams &amp; Sync:</b> Facilitates navigating and verifying code structures between MVC components.</li>
            <li><b>Run Console:</b> Run files or external test scripts directly and view output inside the integrated console window.</li>
            <li><b>External Editor Option:</b> A fallback external launcher can be started from the Integrations tab or right-click menus, executing the configured external command within the active virtual environment when possible.</li>
        </ul>
    """,
    "Workspace Tools": """
        <h1>Workspace Tools</h1>
        <p>The Workspace Tools tab integrates automated analysis utilities for managing project context and history.</p>
        
        <h3>Utilities</h3>
        <ul>
            <li><b>Git Summary:</b> Generates a clean summary of staged and unstaged git status, modifications, and branch information.</li>
            <li><b>Documentation Draft:</b> Generates standard documentation templates based on active project symbols and components.</li>
            <li><b>Changelog Draft:</b> Analyzes git history to draft a clean, human-readable changelog of modifications.</li>
        </ul>
        <p>All generated assistant output can be directly reviewed and saved as markdown files directly into the active workspace directory.</p>
    """,
    "Code Audit & Diagnostics": """
        <h1>Code Audit &amp; Diagnostics</h1>
        <p>Quality and stability tooling built into the interface.</p>
        
        <h3>Anti-Pattern Scanner</h3>
        <p>Scans the active repository for common Python anti-patterns (such as naked except blocks, global statements, or deprecated function usage). Scanned results can be exported directly to a CSV spreadsheet.</p>
        
        <h3>Diagnostics Tool</h3>
        <p>Runs customizable diagnostic and profiling scripts in separate subprocesses. Features include:</p>
        <ul>
            <li><b>Cancellable Execution:</b> Subprocesses can be safely terminated at any time without locking the UI thread.</li>
            <li><b>Crash Protection:</b> Execution runs isolated from the host PyQt6 process, preventing application crashes from script failures.</li>
        </ul>
    """,
    "Integrations & MCP": """
        <h1>Integrations &amp; Model Context Protocol</h1>
        <p>Expose The Librarian capabilities to external AI assistants or IDEs.</p>
        
        <h3>Model Context Protocol (MCP) Server</h3>
        <p>An embedded local MCP-compatible server runs inside the application, exposing search, index status, refresh trigger, and diagnostic tools to client applications.</p>
        
        <h3>Lifecycle &amp; Autostart</h3>
        <ul>
            <li><b>Autostart:</b> Toggle server auto-launch when The Librarian is started.</li>
            <li><b>Status and Probes:</b> Monitor the status of the server port, endpoint calls, and view client connections.</li>
            <li><b>Sync Root:</b> Project root changes automatically propagate to the running MCP server and MVC editor without restarting.</li>
        </ul>
    """,
    "Preferences & Shortcuts": """
        <h1>Preferences &amp; Shortcuts</h1>
        
        <h3>Indexing Settings</h3>
        <p>Open <b>Settings -> Preferences</b> to configure parameters:</p>
        <ul>
            <li><b>File Extensions:</b> Add or remove extensions (e.g., <code>.py</code>, <code>.c</code>, <code>.json</code>) to scan.</li>
            <li><b>Excluded Directories:</b> Add paths to skip (e.g., <code>.venv</code>, <code>node_modules</code>, <code>build</code>).</li>
            <li><b>Process/Thread Workers:</b> Adjust the process count for CPU-bound indexers.</li>
            <li><b>Refresh Interval:</b> Interval in seconds for background indexing. Set to <b>0</b> to disable automatic refreshing.</li>
        </ul>

        <h3>Application Shortcuts</h3>
        <table border="1" cellpadding="6" style="border-collapse: collapse; border-color: #313244; color: #cdd6f4;">
            <tr style="background-color: #313244;">
                <th>Shortcut</th>
                <th>Action</th>
            </tr>
            <tr>
                <td><code>Ctrl + O</code></td>
                <td>Select and Open a new Workspace Folder</td>
            </tr>
            <tr>
                <td><code>Ctrl + S</code></td>
                <td>Save currently open files in MVC Editor</td>
            </tr>
            <tr>
                <td><code>F1</code></td>
                <td>Open Librarian User Guide (Help)</td>
            </tr>
            <tr>
                <td><code>Alt + F4</code></td>
                <td>Quit the Application</td>
            </tr>
        </table>
    """
}


class HelpDialog(QDialog):
    """A premium styled dark-mode Help Dialog containing usage documentation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Librarian User Guide")
        self.resize(750, 520)
        self.setModal(True)
        self.init_ui()

    def init_ui(self) -> None:
        # Stylesheet matching Catppuccin Mocha theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QLineEdit {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
            }
            QListWidget {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #313244;
                color: #f5c2e7;
            }
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #11111b;
            }
            QTextBrowser {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 15px;
                font-size: 13px;
                line-height: 150%;
            }
            QSplitter::handle {
                background-color: #313244;
            }
            QSplitter::handle:hover {
                background-color: #89b4fa;
            }
        """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Splitter to allow resizing sidebar
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Sidebar container widget
        sidebar_widget = QWidget(self)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(8)

        # Search filter
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search help topics...")
        self.search_input.textChanged.connect(self.filter_topics)
        sidebar_layout.addWidget(self.search_input)

        # List of topics
        self.topic_list = QListWidget(self)
        self.topic_list.currentItemChanged.connect(self.display_topic)
        sidebar_layout.addWidget(self.topic_list)

        # Populate topic list
        for topic in HELP_TOPICS.keys():
            self.topic_list.addItem(QListWidgetItem(topic))

        splitter.addWidget(sidebar_widget)

        # Right panel - QTextBrowser
        self.text_browser = QTextBrowser(self)
        self.text_browser.setOpenExternalLinks(True)
        splitter.addWidget(self.text_browser)

        # Set stretch factors and initial splitter sizes
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([180, 520])

        main_layout.addWidget(splitter)

        # Select first topic by default
        if self.topic_list.count() > 0:
            self.topic_list.setCurrentRow(0)

    def display_topic(self, current: QListWidgetItem | None, previous: QListWidgetItem | None = None) -> None:
        """Render the selected topic's HTML content in the text browser."""
        if not current:
            return
        topic_name = current.text()
        html_content = HELP_TOPICS.get(topic_name, "")
        
        # Wrapped HTML template with general formatting
        styled_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                    color: #cdd6f4;
                    background-color: #181825;
                    font-size: 13px;
                    line-height: 1.6;
                }}
                h1 {{
                    color: #89b4fa;
                    font-size: 20px;
                    border-bottom: 1px solid #313244;
                    padding-bottom: 8px;
                    margin-top: 0;
                }}
                h2, h3 {{
                    color: #f5c2e7;
                    font-size: 15px;
                    margin-top: 18px;
                }}
                code {{
                    background-color: #313244;
                    color: #f5e0dc;
                    padding: 2px 5px;
                    border-radius: 3px;
                    font-family: Consolas, 'Courier New', monospace;
                    font-size: 12px;
                }}
                ul, ol {{
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 6px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin-top: 10px;
                }}
                th {{
                    background-color: #313244;
                    color: #89b4fa;
                    text-align: left;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        self.text_browser.setHtml(styled_html)

    def filter_topics(self, filter_text: str) -> None:
        """Filter the topic list based on the search query."""
        query = filter_text.strip().lower()
        self.topic_list.clear()

        for topic, html_content in HELP_TOPICS.items():
            # Match in either topic name or topic description content
            if query in topic.lower() or query in html_content.lower():
                self.topic_list.addItem(QListWidgetItem(topic))

        # Select first matching topic if any exist
        if self.topic_list.count() > 0:
            self.topic_list.setCurrentRow(0)
