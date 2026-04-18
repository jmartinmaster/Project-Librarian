# Project Librarian Master Plan

## Editing Protocol
- Update this file after completing any phase task.
- Update this file before implementation if scope, ordering, or architecture changes.
- Record every key decision change in the Decisions Log with date and reason.
- Keep checkboxes accurate: mark complete only after code and smoke tests pass.
- Keep docs/ focused on active artifacts; move outdated notes to docs/archive/ when needed.

## Project Goals
- Build a standalone desktop application named Project Librarian.
- Provide a local search browser and settings UI.
- Index Python and C source files.
- Support Excel keyword search with configurable key columns.
- Keep the full generated search library in RAM for near-instant searching.
- Enforce MVC architecture, venv-local development, and smoke-test discipline.

## Current Status
- [x] Phase 1 started: scaffold folders, dependency files, and editor defaults.
- [x] Phase 10 started early: workspace instructions added for handoff consistency.
- [x] Phase 2 complete: baseline Python/C/Excel indexers and index manager implemented.
- [x] Phase 3 complete: in-memory search engine implemented.
- [x] Phase 4 complete: main window and search browser wired.
- [x] Phase 5 complete: settings dialog added with persistence.
- [x] Phase 6 complete: Excel browser added.
- [x] Phase 7 complete: main.py entrypoint loads and refreshes in-memory state.
- [x] Phase 8 complete: smoke test suite organized and passing in venv.
- [x] UI enhancement complete: richer search result preview now includes line-context rendering from RAM corpus.
- [x] UI enhancement complete: configurable extension and excluded-directory add/remove controls implemented.
- [x] UI architecture update complete: PyQt6 interfaces now load from Designer .ui files for easier manual editing.
- [x] Refresh worker complete: interval-based background refresh tied to refresh_interval_seconds.
- [x] Lifecycle wiring complete: worker starts with app and stops safely on shutdown/settings restart.
- [x] Smoke tests added for refresh timing and stop behavior.
- [x] UI indicator complete: auto-refresh running/stopped state, interval, and last refresh timestamp visible in main window.
- [x] UI control complete: auto-refresh toggle action in Settings menu.
- [x] Smoke tests added for refresh indicator and status metadata.
- [x] Phase 9 complete: plan and documentation finalization delivered.
- [x] Runbook added for startup/testing/designer workflow.
- [x] Release-readiness checklist added.
- [x] Phase 10 in progress: cross-platform packaging and installer support (Windows + Ubuntu).
- [x] Branding in progress: library-themed icon assets added for app identity.
- [x] Windows packaging support added: build script and guide documented.
- [x] Ubuntu packaging/install support added: build script, local installer script, and guide documented.
- [x] Branded icon assets generated and wired into runtime window/application icon.
- [x] UI enhancement complete: Indexed Library navigation pane added for browse-first discovery before search.
- [x] UI enhancement complete: Library pane now includes live filter input and default-enabled Tree View toggle.
- [x] Packaging UX enhancement complete: dock/taskbar icon identity metadata updated for Ubuntu/Windows rendering.
- [x] Stability fix complete: indexing now handles non-UTF-8 files safely when project root changes.
- [x] UI fix complete: search results table now reliably renders visible columns and row-click selection.
- [x] UX enhancement complete: double-click open and right-click context menus added for search/library items.
- [x] UI enhancement complete: search results now include File Type (py/c/h/csv/etc) alongside Type.
- [ ] UX requirement queued: copy actions should place full absolute containing-folder path on clipboard (no filename/extension).
- [x] Stability fix complete: invalid/malformed spreadsheet files are skipped safely during header discovery and row indexing.
- [x] Observability enhancement complete: skipped-file count/status indicator and skipped-file listing added.
- [ ] Next up: validate packaging outputs on native Windows and Ubuntu hosts.

## Phase Checklist
- [x] Phase 1: Scaffolding and baseline project config
- [x] Phase 2: Indexer implementations (Python, C, Excel, manager)
- [x] Phase 3: Search engine implementation
- [x] Phase 4: Main window and search browser UI
- [x] Phase 5: Settings dialog UI
- [x] Phase 6: Excel browser UI
- [x] Phase 7: Entry point integration
- [x] Phase 8: Smoke tests and AI-assisted generation flow
- [x] Phase 9: Plan and documentation finalization
- [ ] Phase 10: Cross-platform packaging and branding

## Architecture (MVC)
- Model: app/config.py, app/indexer/, app/search/search_engine.py
- View: app/ui/ widgets and dialogs
- Controller: app/indexer/index_manager.py and app/ui/main_window.py orchestration
- Runtime rule: main.py loads index data through IndexManager and retains state.file_corpus, state.symbols, and state.excel_rows in RAM for query operations.

## Directory Layout Target
- app/indexer/ for indexing logic
- app/search/ for search scoring and query behavior
- app/ui/ for presentation layer
- app/dev_tools/ for support scripts
- tests/smoke/ for organized smoke tests
- docs/ for active planning and guidance
- build/ for generated outputs only

## Decisions Log
- 2026-04-18: Fresh standalone rewrite selected instead of reusing old runtime modules.
- 2026-04-18: PyQt6 selected as GUI framework.
- 2026-04-18: pycparser selected for C indexing.
- 2026-04-18: pytest selected for smoke tests.
- 2026-04-18: AI-assisted test generation will use Ollama REST from Python.
- 2026-04-18: docs/PLAN.md is the master handoff document.
- 2026-04-18: .github/copilot-instructions.md added to enforce handoff rules and standards.
- 2026-04-18: Main runtime keeps generated searchable library in memory (RAM) for near-instant search response.
- 2026-04-18: Baseline smoke test suite added under tests/smoke/ and validated with pytest in project venv.
- 2026-04-18: Search preview pane now renders contextual lines from in-memory corpus for faster navigation.
- 2026-04-18: Settings dialog now supports add/remove editing for file extensions and excluded directories.
- 2026-04-18: Main/search/excel/settings interfaces migrated to .ui forms and loaded via PyQt6 uic.loadUi.
- 2026-04-18: IndexManager now includes a safe interval-based background refresh worker with start/stop/restart controls.
- 2026-04-18: App lifecycle now wires worker startup/shutdown, and smoke tests cover refresh timing and safe stop semantics.
- 2026-04-18: Main window now shows live auto-refresh indicator (state, interval, last refresh) and includes an auto-refresh toggle control.
- 2026-04-18: Phase 9 finalized with docs/RUNBOOK.md and docs/RELEASE_CHECKLIST.md.
- 2026-04-18: Phase 10 scope added for Windows/Ubuntu packaging support and branded icon assets.
- 2026-04-18: Added PyInstaller-based packaging scripts for Windows and Ubuntu with docs and local Ubuntu desktop install flow.
- 2026-04-18: Added library-themed SVG icon set and bound app/window icons at runtime.
- 2026-04-18: Added docked Indexed Library navigation pane (files/symbols/excel rows) with click-through routing to search/filter views.
- 2026-04-18: Added library pane filter box and tree/flat toggle (tree enabled by default) for easier browse-first navigation.
- 2026-04-18: Updated app identity metadata (`desktop file name`, `StartupWMClass`, Windows AppUserModelID) to improve dock/taskbar icon rendering.
- 2026-04-18: Hardened indexing against mixed-encoding/malformed files to prevent refresh crashes on new project roots.
- 2026-04-18: Hardened Search Browser table configuration (column count/header/selection) and added UI smoke coverage for visible click-through results.
- 2026-04-18: Added double-click file open and context menus with copy path/reference actions in Search Browser and Indexed Library pane.
- 2026-04-18: Added File Type metadata/column in Search Browser results for quicker language/format identification.
- 2026-04-18: New clipboard-path requirement recorded: default copy should use full system folder path only (exclude filename/extension) to avoid accidental file launch behavior.
- 2026-04-18: Hardened spreadsheet parsing to skip malformed/invalid workbook files without crashing Settings or indexing flows.
- 2026-04-18: Added skipped-file tracking (path/stage/reason), surfaced as status-bar count and Library pane section.

## Out Of Scope (Initial Build)
- MCP server and HTTP dashboard
- REPL and CLI parity with legacy script
- Git operations UI and AI runtime status panels
