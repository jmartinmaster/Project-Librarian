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
- [x] UX requirement complete: copy actions now place full absolute containing-folder path on clipboard (no filename/extension).
- [x] Stability fix complete: invalid/malformed spreadsheet files are skipped safely during header discovery and row indexing.
- [x] Observability enhancement complete: skipped-file count/status indicator and skipped-file listing added.
- [x] Documentation/licensing complete: repository README added, packaging dependency docs refreshed, and GPLv3 headers added to authored files.
- [x] UX enhancement complete: startup splash screen and About dialog added with PyQt6 attribution and startup indexing behavior note.
- [x] Stability fix complete: startup no longer blocks on synchronous indexing; initial refresh now runs in the background.
- [x] Stability fix complete: refresh status polling and manual refresh requests no longer block the UI thread during long indexing runs.
- [x] Settings fix complete: refresh interval now accepts `0` to disable auto-refresh instead of clamping back to a positive value.
- [x] UI fix complete: Indexed Library pane refreshes after background indexing even for larger result sets.
- [ ] Next up: validate packaging outputs on native Windows and Ubuntu hosts.
- [x] Migration tranche complete: ported workspace assistant features from legacy monolith into modular service + UI tab buttons (git summary, docs draft, changelog draft, save output).
- [x] Integration enhancement complete: top-level Integrations tab added for MVC Editor launch controls and MCP server settings/start-stop/probe controls.
- [x] MCP foundation complete: modular local MCP-compatible server added with probe/status/search/refresh/shutdown endpoints.
- [x] MVC embedding enhancement complete: in-app MVC Editor tab now includes direct Model/View/Controller editing sub-tabs with triad load/save.
- [x] Unified workflow enhancement complete: library/search/audit file-open actions now route into embedded MVC Editor by default, with explicit external-open controls retained.
- [x] MVC parity expansion complete: standalone MVC editor capabilities (workspace explorer, inspector/sync navigation, run console, triad discovery, and richer code editing) are now embedded into the integrated tab.
- [x] Root coherence fix complete: Integrations, MVC Editor, and MCP runtime now share the same Librarian project root, and project-root changes propagate across running integrations.
- [x] Native MVC shell integration complete: embedded MVC tab now drops standalone menu/toolbar/workspace tree/console chrome so Librarian controls and tree remain the single primary navigation shell.
- [x] Windows packaging update complete: build scripts now emit a single-file `ProjectLibrarian.exe`, with Windows config/output defaults under `%LOCALAPPDATA%\\Project Librarian`.
- [ ] Phase 11 started: full MVC-compliance refactor planning and staged execution.
- [x] Phase 11 task 1 complete: baseline MVC boundary audit finished and extraction map prepared.
- [x] Phase 11 task 2 complete: `app/controllers/` skeleton added with pass-through wiring in main/search/excel/anti-pattern/diagnostics flows.
- [ ] Next up: Phase 11 task 3 - view decoupling sweep to move remaining business logic out of `app/ui/*`.
- [ ] Deferred until after Phase 11 gate: validate packaging outputs on native Windows and Ubuntu hosts.

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
- [ ] Phase 11: Full MVC compliance refactor (model/view/controller separation + utility extraction)

## Phase 11 Implementation Plan (One Task At A Time)
### Goal
- Complete migration to strict MVC boundaries where view widgets render and emit intent only, controllers orchestrate workflows, and model/services own business/data logic.

### Sequenced Tasks
1. Baseline MVC boundary audit
   - Inventory business logic currently inside `app/ui/*`.
   - Identify orchestration logic currently mixed between `main.py`, `app/ui/main_window.py`, and widget classes.
   - Produce extraction map for Search, Library navigation, Anti-pattern scan, Diagnostics, and Settings workflows.
2. Controller layer skeleton
   - Add `app/controllers/` package and typed controller contracts.
   - Create controller modules for search workflow, library navigation workflow, anti-pattern audit workflow, diagnostics workflow, and app lifecycle/settings workflow.
   - Keep existing behavior unchanged while wiring pass-through delegation.
3. View decoupling pass
   - Refactor each UI widget to delegate business actions to controllers.
   - Restrict view code to UI binding, state display, and signal forwarding.
   - Remove direct non-view concerns from widgets (filesystem/git/process/domain logic).
4. Model/service normalization pass
   - Keep domain/data logic in model-side modules (`app/indexer/`, `app/search/`, `app/config.py`, and service/util packages).
   - Extract shared utility helpers for path resolution, export operations, and error/report formatting where reused by multiple controllers.
   - Enforce no PyQt dependencies in model/service utilities.
5. Smoke test migration and stabilization
   - Update smoke tests under `tests/smoke/` to validate behavior via controller seams and retained UI contracts.
   - Adjust tests affected by dependency injection/controller wiring changes.
   - Run full smoke suite and close regressions before marking the phase complete.

### Phase 11 Exit Criteria
- No business/domain logic remains embedded in view widgets.
- Controllers own orchestration paths for Search, Library, Anti-pattern, Diagnostics, and Settings.
- Smoke tests pass with updated coverage for controller-driven behavior.
- `docs/PLAN.md` checklist and decisions log updated with completed migration notes.

## Architecture (MVC)
- Model: `app/config.py`, `app/indexer/`, `app/search/`, and domain-oriented service/util modules with no Qt dependencies
- View: `app/ui/` widgets/dialogs/.ui forms for rendering, user input capture, and signal emission only
- Controller (target): `app/controllers/` workflow orchestrators and app lifecycle coordination
- Controller (transition): `app/indexer/index_manager.py` and `app/ui/main_window.py` orchestration being migrated to `app/controllers/`
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
- 2026-04-18: Added scope for README refresh, packaging dependency refresh, GPLv3 headers across authored files, and PyQt6 attribution in splash/About UX.
- 2026-04-18: Added repository README, refreshed packaging requirements/docs, added splash/About attribution text, and applied GPLv3 headers across authored files except read-only reference modules.
- 2026-04-27: Moved initial startup refresh off the UI thread by enabling immediate background worker refresh and UI auto-sync on refresh-count changes.
- 2026-04-27: Reduced IndexManager refresh lock scope to state publication only, added non-blocking async manual refresh requests, and stopped automatic heavy UI refresh work after each background indexing cycle.
- 2026-04-27: Allowed a zero-second refresh interval in SettingsDialog so users can disable auto-refresh through the UI and persist that value correctly.
- 2026-04-27: Removed the Indexed Library auto-refresh size gate so completed background refreshes always repopulate the sidebar; tree updates are now wrapped with setUpdatesEnabled for less repaint churn.
- 2026-07-08: Fixed copy-path clipboard behavior across search/library/audit views to copy absolute containing-folder paths instead of filenames.
- 2026-07-08: Added refresh error reporting in IndexManager/MainWindow so worker/manual refresh failures are surfaced instead of silently swallowed.
- 2026-07-08: Switched config storage to platform-aware directories (APPDATA on Windows, Application Support on macOS, ~/.config on Linux).
- 2026-07-08: Updated diagnostics subprocess cancellation and runner lifecycle to avoid Windows-only kill behavior and eliminate indefinite post-profile hangs.
- 2026-07-08: Compared the legacy monolith feature surface and ported high-value workspace assistant flows into modular files (`app/services/workspace_service.py`, `app/ui/workspace_browser.py`) with button-driven UI wiring.
- 2026-07-08: Added `Integrations` tab for external MVC Editor path/launch workflow plus MCP server setup, save, start/stop, and probe controls.
- 2026-07-08: Ported a modular local MCP-compatible server runtime (`app/services/librarian_mcp_server.py`) and subprocess lifecycle manager (`app/services/mcp_server_manager.py`) wired to app config and autostart.
- 2026-07-08: Added direct in-app MVC Editor embedding (`app/ui/mvc_editor_tab.py`) with triad file workflow and wired it as a primary top tab in the main window.
- 2026-07-08: Unified file-open workflow so Search Browser, Indexed Library, and Code Audit open files in the embedded MVC Editor; kept explicit external-open path for user-controlled handoff.
- 2026-07-08: Scope expanded to full standalone MVC editor feature parity inside Project Librarian before next compile/release handoff.
- 2026-07-08: Imported standalone MVC Sync internals into `app/ui/mvc_sync/` and wrapped them in `MVCEditorTab` so in-app editing includes workspace explorer, triad discovery, inspector navigation, sync tooling, and run console while preserving Librarian open-routing.
- 2026-07-08: Removed independent integrations root behavior by treating project root as the single shared root for MVC + MCP, added root-change callback wiring in main window, and switched folder picker to non-native dialog mode to avoid Windows COM dialog crashes.
- 2026-07-08: Applied full native integration mode to MVC tab by suppressing standalone shell surfaces and inheriting host tab theming to keep Librarian as the single unified interface shell.
- 2026-07-08: Switched Windows packaging to PyInstaller one-file output and moved Windows runtime config/artifact defaults to `%LOCALAPPDATA%\\Project Librarian` for portable executable relocation without adjacent support folders.
- 2026-07-08: Re-prioritized roadmap to execute a dedicated Phase 11 full MVC-compliance refactor in sequenced slices before final packaging validation.
- 2026-07-08: Completed Phase 11 Task 1 boundary audit and confirmed controller extraction priorities in this order: Search, Main Window/Library, Anti-pattern, Diagnostics, Settings/Lifecycle.
- 2026-07-08: Completed Phase 11 Task 2 by introducing `app/controllers/` seams and delegating key workflows from views to controller pass-through methods.
- 2026-07-08: Advanced Phase 11 Task 3 with broader view decoupling in Search/Main/Excel/Anti-pattern/Settings by routing workflow logic through dedicated controllers.
- 2026-07-08: Continued Phase 11 Task 3 by moving CSV export and anti-pattern scan orchestration out of views and into controller methods.

## Out Of Scope (Initial Build)
- REPL and CLI parity with legacy script
- Git operations UI and AI runtime status panels
