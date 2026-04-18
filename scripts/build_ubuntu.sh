#!/usr/bin/env bash
# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Project Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.

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
