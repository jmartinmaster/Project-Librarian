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

# Release Readiness Checklist

## Environment
- [x] `.venv` exists and dependencies install successfully from `requirements.txt`.
- [x] App starts with `./run.sh`.
- [x] App starts with `.venv/bin/python main.py`.

## Functional Validation
- [x] Search browser returns file/symbol/excel results.
- [x] Search result preview shows line context.
- [x] Settings dialog saves project/indexing/excel settings.
- [x] Auto-refresh status indicator updates in main window.
- [x] Auto-refresh toggle enables/disables worker safely.
- [x] Help Dialog opens via `F1` shortcut or Help -> Librarian User Guide menu item, and displays the guide.

## Test Validation
- [x] Smoke suite passes: `.venv/bin/python -m pytest tests/smoke -v`.
- [x] New/changed features include smoke tests under `tests/smoke/`.

## Project Hygiene
- [x] `docs/PLAN.md` current status and checklist are up to date.
- [x] Active docs are kept in `docs/`; stale docs archived/removed.
- [x] Generated outputs are stored under `build/` only.
- [x] No modifications were made to `project_librarian.py` or `symbol_index.py`.

## Packaging/Handoff
- [x] `run.sh` is executable.
- [x] VS Code interpreter path points to `.venv/bin/python`.
- [x] Handoff notes include current phase and next work item.
- [x] Windows packaging script runs on Windows and outputs `dist/ProjectLibrarian.exe`.
- [ ] Ubuntu packaging script runs and outputs `dist/ProjectLibrarian/`.
- [ ] Ubuntu local installer script creates launcher and desktop entry.
