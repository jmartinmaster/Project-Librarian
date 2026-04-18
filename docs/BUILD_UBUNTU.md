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
2. Install app dependencies:
   - `.venv/bin/pip install -r requirements.txt`
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
- Runtime includes UI forms and icon assets.
- Desktop entry includes `StartupWMClass=ProjectLibrarian` to improve dock/taskbar icon matching.
