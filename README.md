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

Project Librarian is a local PyQt6 desktop application for indexing source code and spreadsheet content into an in-memory search library. It provides fast, offline browsing of Python, C, Markdown, text, JSON, CSV, and Excel content from a project folder, along with an embedded code editor, workspace assistant, MVC audit tools, and a local MCP-compatible server.

## What It Does

### Search and Indexing
- Indexes Python and C symbols.
- Keeps file corpus, symbol metadata, and Excel keyword rows in memory for near-instant searching.
- Provides a Search Browser, Excel Browser, and Indexed Library pane for browse-first navigation.
- Displays File Type alongside result type for quicker language and format identification.
- Tracks skipped files so malformed or unreadable inputs do not crash refreshes.
- Refreshes the index on demand and keeps it current with a configurable background worker.

### Workspace Assistant
- Generates git summaries, documentation drafts, and changelog drafts from the active project root.
- Saves generated output to the project folder through the Workspace tab.

### Integrations
- Launches an external MVC Editor from a configurable executable path.
- Controls a local MCP-compatible server (start, stop, probe, configure) from the Integrations tab.
- Project root changes propagate automatically to all running integrations.

### Embedded MVC Editor
- Hosts a full-featured code editor directly inside Project Librarian.
- Includes a workspace explorer, triad file discovery, inspector and sync navigation, a run console, and model/view/controller sub-tabs for triad load and save.
- File-open actions from Search Browser, Indexed Library, and Code Audit route into the embedded editor by default; explicit external-open controls are retained for handoff.

### Code Audit and Diagnostics
- Scans the project for anti-pattern occurrences with configurable rules.
- Runs profiling and diagnostics sessions, with a subprocess-safe cancellation flow.
- Surfaces results in dedicated Anti-pattern and Diagnostics browser tabs.

### MCP Server
- Runs a modular local MCP-compatible server exposing probe, status, search, refresh, and shutdown endpoints.
- Server lifecycle (start/stop/autostart) is managed from the Integrations tab and persisted in app config.

## Startup Behavior

When Project Librarian starts with a fresh configuration, it uses the folder it was opened from as the initial index root. After you save a project root in settings, later launches reuse that saved location until you change it. The initial indexing run executes in the background so the UI is immediately responsive.

Configuration is stored in a platform-aware location: `%APPDATA%\Project Librarian` on Windows, `~/Library/Application Support/Project Librarian` on macOS, and `~/.config/Project Librarian` on Linux.

## Quick Start

### Development

1. Create the virtual environment: `py -3 -m venv .venv` on Windows or `python3 -m venv .venv` on Linux.
2. Install runtime dependencies: `pip install -r requirements.txt`
3. Launch the desktop app: `python main.py`

### Packaging

1. Install packaging dependencies: `pip install -r requirements-packaging.txt`
2. Build on Windows with `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`
   - Produces a single-file `ProjectLibrarian.exe`; runtime config defaults to `%LOCALAPPDATA%\Project Librarian`.
3. Build on Ubuntu with `bash scripts/build_ubuntu.sh`

## Repository Layout

- `app/indexer/`: indexing logic and refresh orchestration
- `app/search/`: in-memory search engine
- `app/controllers/`: MVC workflow controllers for search, library, audit, diagnostics, and settings
- `app/services/`: business-logic services for workspace, MCP server, anti-pattern, and diagnostics operations
- `app/ui/`: PyQt6 windows, dialogs, forms, and assets
- `tests/smoke/`: smoke coverage for model, controller, and UI behavior
- `docs/`: active build, run, release, and planning documents

## Licensing

Project Librarian is licensed under the GNU GPL v3.0 or later. See `LICENSE` for the full text.

This application is built with PyQt6. The app splash screen and About dialog include PyQt6 attribution to align the packaged application with the framework requirements already chosen for this project.