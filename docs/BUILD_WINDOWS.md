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

# Build On Windows

## Prerequisites
- Windows 10/11
- Python 3.11+ installed
- PowerShell

## Steps
1. Clone/copy this repository to the Windows machine.
2. Create virtual environment:
   - `py -3 -m venv .venv`
3. Install packaging dependencies:
   - `.venv\Scripts\pip install -r requirements-packaging.txt`
4. Run packaging script:
   - `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`

## Output
- Packaged app folder: `dist/ProjectLibrarian/`
- Start executable: `dist/ProjectLibrarian/ProjectLibrarian.exe`

## Notes
- Build on Windows for Windows distribution.
- `requirements-packaging.txt` now layers runtime dependencies with packaging-only tools so release builds stay aligned with the app runtime.
- The package includes `.ui` forms and icon assets used by runtime UI.
- On first launch with a fresh config, indexing starts from the folder where the executable was opened.
