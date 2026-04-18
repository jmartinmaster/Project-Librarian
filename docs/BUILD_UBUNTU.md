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

# Build And Install On Ubuntu

## Prerequisites
- Ubuntu 22.04+ (or compatible)
- Python 3.11+ with venv support
- Desktop environment for launcher integration

Install prerequisite packages:
- `sudo apt update`
- `sudo apt install -y python3 python3-venv`

## Build Steps
1. Create virtual environment:
   - `python3 -m venv .venv`
2. Install packaging dependencies:
   - `.venv/bin/pip install -r requirements-packaging.txt`
3. Build distributable:
   - `bash scripts/build_ubuntu.sh`

## Local Install Steps
1. Install to user-local paths with desktop entry:
   - `bash scripts/install_ubuntu_local.sh`
2. Launch from app menu or terminal:
   - `project-librarian`
3. If a stale icon is shown after updates, rerun installer and restart shell session:
   - `bash scripts/install_ubuntu_local.sh`

## Output
- Build folder: `dist/ProjectLibrarian/`
- Local install dir: `~/.local/opt/project-librarian/`
- Desktop entry: `~/.local/share/applications/project-librarian.desktop`

## Notes
- Build on Ubuntu for Ubuntu distribution.
- `requirements-packaging.txt` includes both runtime and packaging dependencies for reproducible local builds.
- Runtime includes UI forms and icon assets.
- Desktop entry includes `StartupWMClass=ProjectLibrarian` to improve dock/taskbar icon matching.
- On first launch with a fresh config, indexing starts from the folder where the application was opened.
