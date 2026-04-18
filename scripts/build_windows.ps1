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
  --windowed `
  --name ProjectLibrarian `
  --add-data "$RepoRoot\app\ui\forms;app\ui\forms" `
  --add-data "$RepoRoot\app\ui\assets;app\ui\assets" `
  (Join-Path $RepoRoot "main.py")

Write-Host "Windows build complete: $RepoRoot\dist\ProjectLibrarian"
