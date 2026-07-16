# Copyright (C) 2026 The Librarian contributors
#
# This file is part of The Librarian.
#
# The Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with The Librarian. If not, see <https://www.gnu.org/licenses/>.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
  Write-Error "Missing venv python at $VenvPython. Create it with: py -3 -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

& $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements-packaging.txt")
& $VenvPython -m PyInstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name TheLibrarian `
  --add-data "$RepoRoot\app\views\forms;app\views\forms" `
  --add-data "$RepoRoot\app\views\assets;app\views\assets" `
  (Join-Path $RepoRoot "main.py")

Write-Host "Windows build complete: $RepoRoot\dist\TheLibrarian.exe"
