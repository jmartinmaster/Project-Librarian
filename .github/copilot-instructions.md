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

# Project Librarian Workspace Instructions

## Handoff Protocol
- Read docs/PLAN.md before making any code changes.
- Identify the active phase and task in docs/PLAN.md.
- Review the latest active notes in docs/ before editing code.
- If scope must change, update docs/PLAN.md first, then implement.

## Follow The Plan Rule
- The implementation plan in docs/PLAN.md is authoritative.
- Do not bypass or reorder tasks without recording the change in the Decisions Log.

## Architecture Rules
- Keep MVC boundaries strict.
- Model layer: app/indexer/, app/search/search_engine.py, app/config.py.
- View layer: app/ui/ widgets and dialogs only.
- Controller layer: app/indexer/index_manager.py and app/ui/main_window.py orchestration logic.
- Business logic must not be implemented inside view widgets.

## Code Quality Rules
- No shortcuts: write complete code, not placeholders.
- Do not leave TODO-only stubs in production modules.
- Keep imports clean and remove unused imports.
- Use PEP 8 and Google-style docstrings for public classes and functions.

## Testing Rules
- Add smoke tests as each phase is implemented.
- Store smoke tests under tests/smoke/ in the correct subfolder.
- Run pytest tests/smoke/ after relevant changes.
- AI-generated tests must be reviewed and kept readable before commit.

## Documentation Rules
- Keep docs/ focused on active plans, notes, and current results.
- Archive or remove stale docs that are no longer active.
- Add module README.md files for package folders.
- Store generated outputs (index, corpus, history, generated reports) under build/ only.

## Python Environment Rules
- The project venv must live at .venv/ in the repository.
- Use .venv/bin/python and .venv/bin/pytest for commands.
- Do not use global pip for project dependencies.
- Ensure terminals default to the project venv.

## Source Of Truth Files
- project_librarian.py and symbol_index.py are read-only references.
- Do not modify project_librarian.py or symbol_index.py while building the standalone app.

## Git Workflow Rules
- Use feature branches named feature/phase-N-description.
- Use short imperative commit messages.
- Commit at logical task boundaries and include docs/PLAN.md updates when phase state changes.

## AI Test Generation Rules
- Use app/dev_tools/test_generator.py for local AI-assisted smoke test generation.
- Generate tests into the matching tests/smoke/ subfolder only.
- Validate generated tests with pytest before handoff.
