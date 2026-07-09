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

Project Librarian is a local PyQt6 desktop application for indexing source code and spreadsheet content into an in-memory search library. It is intended for fast, offline browsing of Python, C, Markdown, text, JSON, CSV, and Excel content from a project folder.

## What It Does

### Indexing and Search
- Indexes Python and C symbols, plus Markdown, text, JSON, CSV, and Excel content.
- Keeps the full file corpus, symbol metadata, and Excel keyword rows in memory for near-instant searching.
- Provides line-context preview in search results rendered directly from the in-memory corpus.
- Tracks skipped files so malformed or unreadable inputs do not crash index refreshes.
- Refreshes the index on demand or automatically via a configurable background worker.

### Navigation
- **Search Browser** – full-text and symbol search with file-type column, double-click to open, and right-click context menus for copy path/reference actions.
- **Excel Browser** – keyword search across indexed spreadsheet rows with configurable key columns.
- **Indexed Library** pane – browse-first tree/flat view of all indexed files and symbols with live filter input.

### Workspace Assistant
- Generates git summaries, documentation drafts, and changelog drafts for the current project root.
- Save-to-file output for each generated artifact.

### Integrations
- **MVC Editor tab** – full embedded MVC editor with workspace explorer, triad discovery, inspector/sync navigation, code editing sub-tabs (Model / View / Controller), and a run console. All file-open actions from Search Browser, Indexed Library, and Code Audit route into the embedded editor by default.
- **MCP Server** – modular local MCP-compatible server with search, refresh, probe, and shutdown endpoints. Start/stop/probe controls are available in the Integrations tab. The server shares the same project root as the rest of the application.

### Diagnostics and Code Quality
- **Anti-pattern Scanner** – detects common code anti-patterns across the indexed project with CSV export.
- **Diagnostics** – runs configurable profiling/diagnostic scripts with cancellable subprocess lifecycle.

### Settings and Configuration
- Configurable file extensions and excluded-directory lists with add/remove controls.
- Platform-aware configuration storage (`%APPDATA%` on Windows, `Application Support` on macOS, `~/.config` on Linux).
- Refresh interval accepts `0` to disable auto-refresh.
- Auto-refresh toggle in the Settings menu with live status indicator (state, interval, last refresh time).

## Startup Behavior

When Project Librarian starts with a fresh configuration, it uses the folder it was opened from as the initial index root. After you save a project root in settings, later launches reuse that saved location until you change it. The initial index refresh runs in the background so the UI is immediately responsive.

## Quick Start

### Development

1. Create the virtual environment: `py -3 -m venv .venv` on Windows or `python3 -m venv .venv` on Linux.
2. Install runtime dependencies: `pip install -r requirements.txt`
3. Launch the desktop app: `python main.py`

### Packaging

1. Install packaging dependencies: `pip install -r requirements-packaging.txt`
2. Build on Windows with `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`
3. Build on Ubuntu with `bash scripts/build_ubuntu.sh`

## Repository Layout

- `app/indexer/`: indexing logic and background refresh orchestration
- `app/search/`: in-memory search engine
- `app/controllers/`: MVC controller layer – orchestrates Search, Library, Anti-pattern, Diagnostics, and Settings workflows
- `app/services/`: workspace assistant, anti-pattern analysis, diagnostics, MCP server, and server lifecycle manager
- `app/ui/`: PyQt6 windows, dialogs, forms, and assets (Search Browser, Excel Browser, Indexed Library, Workspace Assistant, Integrations, MVC Editor)
- `tests/smoke/`: smoke coverage for model, controller, and UI behavior
- `docs/`: active build, run, release, and planning documents
- `scripts/`: platform build scripts for Windows and Ubuntu packaging

## Licensing

Project Librarian is licensed under the GNU GPL v3.0 or later. See `LICENSE` for the full text.

This application is built with PyQt6. The app splash screen and About dialog include PyQt6 attribution to align the packaged application with the framework requirements already chosen for this project.