#!/usr/bin/env bash
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
  --name TheLibrarian \
  --add-data "${REPO_ROOT}/app/views/forms:app/views/forms" \
  --add-data "${REPO_ROOT}/app/views/assets:app/views/assets" \
  "${REPO_ROOT}/main.py"

echo "Ubuntu build complete: ${REPO_ROOT}/dist/TheLibrarian"
