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

# Runbook

## Quick Start
1. Create and install venv dependencies:
   - `python3 -m venv .venv`
   - `.venv/bin/pip install -r requirements.txt`
2. Start the app with the project launcher:
   - `./run.sh`

## Alternative Start Command
- `.venv/bin/python main.py`

## Run Smoke Tests
- `.venv/bin/python -m pytest tests/smoke -v`

## Build For Windows
- On a Windows machine, run:
   - `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`

## Build And Install For Ubuntu
- Build distributable:
   - `bash scripts/build_ubuntu.sh`
- Install locally with desktop entry and icon:
   - `bash scripts/install_ubuntu_local.sh`

## UI Editing Workflow (PyQt6 Designer)
- UI form files are under `app/ui/forms/`.
- Runtime widgets load forms via `PyQt6.uic.loadUi`.
- Edit `.ui` files for layout changes, keep business logic in Python modules.

## Auto-Refresh Worker Notes
- Worker interval is controlled by `refresh_interval_seconds` in settings.
- Worker status is shown in the main window status bar.
- Worker can be toggled in the Settings menu via `Auto Refresh Enabled`.

## Troubleshooting
- If `python main.py` fails due to system/snap Python mismatch, run with venv:
  - `.venv/bin/python main.py`
- Ensure `.venv/bin/python` exists before launching.
