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
