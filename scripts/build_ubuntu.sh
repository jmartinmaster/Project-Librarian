#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Missing venv python at ${VENV_PYTHON}" >&2
  echo "Create it: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

"${VENV_PYTHON}" -m pip install -r "${REPO_ROOT}/requirements-packaging.txt"
"${VENV_PYTHON}" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name ProjectLibrarian \
  --add-data "${REPO_ROOT}/app/ui/forms:app/ui/forms" \
  --add-data "${REPO_ROOT}/app/ui/assets:app/ui/assets" \
  "${REPO_ROOT}/main.py"

echo "Ubuntu build complete: ${REPO_ROOT}/dist/ProjectLibrarian"
