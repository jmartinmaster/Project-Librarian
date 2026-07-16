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
DIST_DIR="${REPO_ROOT}/dist/TheLibrarian"
INSTALL_DIR="${HOME}/.local/opt/the-librarian"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

if [[ ! -d "${DIST_DIR}" ]]; then
  echo "Build output not found at ${DIST_DIR}. Run: bash scripts/build_ubuntu.sh" >&2
  exit 1
fi

mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${APP_DIR}" "${ICON_DIR}"
rm -rf "${INSTALL_DIR:?}"/*
cp -r "${DIST_DIR}"/* "${INSTALL_DIR}/"

if [[ -f "${REPO_ROOT}/app/views/assets/library_icon.svg" ]]; then
  cp "${REPO_ROOT}/app/views/assets/library_icon.svg" "${ICON_DIR}/the-librarian.svg"
fi

cat > "${BIN_DIR}/the-librarian" <<'EOF'
#!/usr/bin/env bash
exec "$HOME/.local/opt/the-librarian/TheLibrarian" "$@"
EOF
chmod +x "${BIN_DIR}/the-librarian"

cat > "${APP_DIR}/the-librarian.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=The Librarian
Comment=Local source and spreadsheet search browser
Exec=the-librarian
Icon=the-librarian
StartupWMClass=TheLibrarian
Terminal=false
Categories=Development;Utility;
EOF

update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true

echo "Installed The Librarian locally."
echo "Launch from app menu or run: the-librarian"
