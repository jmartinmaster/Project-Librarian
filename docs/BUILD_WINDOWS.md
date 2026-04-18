# Build On Windows

## Prerequisites
- Windows 10/11
- Python 3.11+ installed
- PowerShell

## Steps
1. Clone/copy this repository to the Windows machine.
2. Create virtual environment:
   - `py -3 -m venv .venv`
3. Install app dependencies:
   - `.venv\Scripts\pip install -r requirements.txt`
4. Run packaging script:
   - `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`

## Output
- Packaged app folder: `dist/ProjectLibrarian/`
- Start executable: `dist/ProjectLibrarian/ProjectLibrarian.exe`

## Notes
- Build on Windows for Windows distribution.
- The package includes `.ui` forms and icon assets used by runtime UI.
