#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist/ProjectLibrarian"
INSTALL_DIR="${HOME}/.local/opt/project-librarian"
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

if [[ -f "${REPO_ROOT}/app/ui/assets/library_icon.svg" ]]; then
  cp "${REPO_ROOT}/app/ui/assets/library_icon.svg" "${ICON_DIR}/project-librarian.svg"
fi

cat > "${BIN_DIR}/project-librarian" <<'EOF'
#!/usr/bin/env bash
exec "$HOME/.local/opt/project-librarian/ProjectLibrarian" "$@"
EOF
chmod +x "${BIN_DIR}/project-librarian"

cat > "${APP_DIR}/project-librarian.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Project Librarian
Comment=Local source and spreadsheet search browser
Exec=project-librarian
Icon=project-librarian
StartupWMClass=ProjectLibrarian
Terminal=false
Categories=Development;Utility;
EOF

update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true

echo "Installed Project Librarian locally."
echo "Launch from app menu or run: project-librarian"
