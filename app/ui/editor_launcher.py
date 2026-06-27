# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#

"""Service to launch files in external editors at specified line numbers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import AppConfig


def launch_editor(file_path: Path | str, line_number: int | None, config: AppConfig) -> bool:
    """Attempt to launch the file in an external editor.
    
    If config.external_editor_cmd is configured, substitutes {file} and {line}
    and executes it. Otherwise, tries to auto-detect VS Code ('code') or
    Sublime Text ('subl') in the system PATH.
    
    Returns:
        bool: True if command execution was triggered, False otherwise.
    """
    path_str = str(Path(file_path).resolve())
    line_str = str(line_number) if line_number is not None else "1"

    cmd_template = config.external_editor_cmd.strip()

    if not cmd_template:
        # Try auto-detection
        if shutil.which("code"):
            cmd_template = 'code -g "{file}:{line}"'
        elif shutil.which("subl"):
            cmd_template = 'subl "{file}:{line}"'

    if not cmd_template:
        return False

    cmd = cmd_template.replace("{file}", path_str).replace("{line}", line_str)

    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            
        subprocess.Popen(cmd, shell=True, creationflags=creationflags)
        return True
    except Exception:
        return False
