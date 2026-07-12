<!--
Copyright (C) 2026 Project Librarian contributors

This file is part of Project Librarian.

Project Librarian is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Project Librarian is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.
-->

# Project Librarian

Project Librarian is a local PyQt6 desktop application for indexing source code and spreadsheet content into an in-memory search library. It provides fast, offline browsing of Python, C, Markdown, text, JSON, CSV, and Excel content from a project folder, along with an embedded code editor, workspace assistant, MVC audit tools, a local MCP-compatible server, and an in-app help system.

## Architecture & Design

### Strict MVC Separation
The codebase implements a strict Model-View-Controller (MVC) architecture:
- **Model:** Retains business logic, spreadsheet parsing, MCP server, and workspace indexing capabilities (implemented in `app/models/` and `app/indexer/`), completely decoupled from PyQt6 GUI elements.
- **View:** Manages presentation, layout (.ui forms loaded dynamically), widget setups, and user signal emissions (located in `app/views/`).
- **Controller:** Orchestrates user flows, bridging data structures between the models and UI controls (located in `app/controllers/`).

## What It Does

### Search and Indexing
- **Process-Level Parallelism:** Uses `ProcessPoolExecutor` to offload CPU-bound token indexing and syntax parsing to child processes. This bypasses the Python GIL (Global Interpreter Lock) for true multi-core speed, isolates indexer errors, and guarantees a completely stutter-free PyQt6 user interface.
- Keeps the full file corpus, symbol metadata, and Excel keyword rows in memory for near-instant searching.
- Provides line-context preview in search results rendered directly from the in-memory corpus.
- Displays File Type alongside result type for quicker language and format identification.
- Tracks skipped files so malformed or unreadable inputs do not crash refreshes.
- Refreshes the index on demand and keeps it current with a configurable background worker.

### Navigation and UI
- **Search Browser** – full-text and symbol search with file-type column, double-click to open, and right-click context menus.
- **Excel Browser** – keyword search across indexed spreadsheet rows with configurable key columns.
- **Indexed Library** pane – browse-first tree/flat view of all indexed files and symbols with live filter input.
- **Clipboard Actions** – right-click context menus copy the absolute **containing-folder path** to the clipboard (rather than the file path) to prevent accidental run/open actions.
- **In-App User Guide** – press `F1` or select `Help -> Librarian User Guide` to open the premium dark-mode, searchable help system directly inside the app.

### Workspace Assistant
- Generates git summaries, documentation drafts, and changelog drafts from the active project root.
- Saves generated output to the project folder through the Workspace Tools tab.

### Integrations and Servers
- **Embedded MVC Editor** – hosts a full-featured code editor directly inside Project Librarian, with a workspace explorer, triad file discovery, inspector/sync navigation, run console, and Model/View/Controller sub-tabs for triad load and save.
- **External MVC Editor launcher** – launches an external MVC Editor from a configurable folder path (runs the editor’s `main.py`, using its `.venv` Python when available).
- **MCP Server** – runs a modular local MCP-compatible server exposing probe, status, search, refresh, and shutdown endpoints. The server lifecycle (start/stop/autostart) is managed from the Integrations tab and persisted in app config.
- Project root changes propagate automatically to all running integrations.

### Code Audit and Diagnostics
- **Anti-pattern Scanner** – detects common code anti-patterns across the indexed project with CSV export.
- **Diagnostics** – runs configurable profiling/diagnostic scripts with a cancellable, subprocess-safe lifecycle.

### Settings and Configuration
- Configurable file extensions and excluded-directory lists with add/remove controls.
- Platform-aware configuration storage:
  - **Windows:** `%LOCALAPPDATA%\Project Librarian\` for packaged builds (otherwise `%APPDATA%\`)
  - **macOS:** `~/Library/Application Support/`
  - **Linux:** `~/.config/`
- Refresh interval accepts `0` to disable auto-refresh.
- Auto-refresh toggle in the Settings menu with live status indicator (state, interval, last refresh time).

## Startup Behavior

When Project Librarian starts with a fresh configuration, it uses the folder it was opened from as the initial index root. After you save a project root in settings, later launches reuse that saved location until you change it. On first run (when no snapshot exists yet), Project Librarian builds the initial index and snapshot before launching the main window; subsequent refreshes run in the background so the UI stays responsive.

## Quick Start

### Development

1. Create the virtual environment: `py -3 -m venv .venv` on Windows or `python3 -m venv .venv` on Linux.
2. Install runtime dependencies: `pip install -r requirements.txt`
3. Launch the desktop app: `python main.py`
4. Run tests:
   - **Sequentially**: `pytest`
   - **In parallel**: `python run_tests_parallel.py`
     - Specify the number of workers: `python run_tests_parallel.py -w 4`
     - Run a specific folder or file: `python run_tests_parallel.py tests/smoke/ui`
     - Pass options directly to pytest: `python run_tests_parallel.py -- -k test_workspace`

### Packaging

1. Install packaging dependencies: `pip install -r requirements-packaging.txt`
2. Build on Windows with `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`
   - Produces a single-file `ProjectLibrarian.exe`; runtime config defaults to `%LOCALAPPDATA%\Project Librarian`.
3. Build on Ubuntu with `bash scripts/build_ubuntu.sh`

## Repository Layout

- `app/indexer/`: indexing logic and background refresh orchestration
- `app/search/`: in-memory search engine
- `app/controllers/`: MVC controller layer – orchestrates Search, Library, Anti-pattern, Diagnostics, and Settings workflows
- `app/models/`: workspace assistant, anti-pattern analysis, diagnostics, MCP server, and server lifecycle manager
- `app/views/`: PyQt6 windows, dialogs, forms, and assets (Search Browser, Excel Browser, Indexed Library, Workspace Assistant, Integrations, MVC Editor)
- `tests/smoke/`: smoke coverage for model, controller, and UI behavior
- `docs/`: active build, run, release, and planning documents
- `scripts/`: platform build scripts for Windows and Ubuntu packaging

## Licensing

Project Librarian is licensed under the GNU GPL v3.0 or later. See `LICENSE` for the full text.

This application is built with PyQt6. The app splash screen and About dialog include PyQt6 attribution to align the packaged application with the framework requirements already chosen for this project.

This application optionally uses `libcst` for Concrete Syntax Tree (CST) parsing, which is licensed under the MIT License.