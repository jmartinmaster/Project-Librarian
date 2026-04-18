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
- [ ] `.venv` exists and dependencies install successfully from `requirements.txt`.
- [ ] App starts with `./run.sh`.
- [ ] App starts with `.venv/bin/python main.py`.

## Functional Validation
- [ ] Search browser returns file/symbol/excel results.
- [ ] Search result preview shows line context.
- [ ] Settings dialog saves project/indexing/excel settings.
- [ ] Auto-refresh status indicator updates in main window.
- [ ] Auto-refresh toggle enables/disables worker safely.

## Test Validation
- [ ] Smoke suite passes: `.venv/bin/python -m pytest tests/smoke -v`.
- [ ] New/changed features include smoke tests under `tests/smoke/`.

## Project Hygiene
- [ ] `docs/PLAN.md` current status and checklist are up to date.
- [ ] Active docs are kept in `docs/`; stale docs archived/removed.
- [ ] Generated outputs are stored under `build/` only.
- [ ] No modifications were made to `project_librarian.py` or `symbol_index.py`.

## Packaging/Handoff
- [ ] `run.sh` is executable.
- [ ] VS Code interpreter path points to `.venv/bin/python`.
- [ ] Handoff notes include current phase and next work item.
- [ ] Windows packaging script runs on Windows and outputs `dist/ProjectLibrarian/`.
- [ ] Ubuntu packaging script runs and outputs `dist/ProjectLibrarian/`.
- [ ] Ubuntu local installer script creates launcher and desktop entry.
