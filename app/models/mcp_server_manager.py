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
"""Process manager for launching and stopping the local MCP server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.indexer.index_manager import IndexManager


class MCPServerManager:
    """Manage lifecycle of the local Project Librarian MCP server subprocess."""

    def __init__(self, index_manager: IndexManager) -> None:
        self.index_manager = index_manager
        self._process: subprocess.Popen[str] | None = None

    def is_running(self) -> bool:
        """Return True if the MCP server subprocess is active."""
        return self._process is not None and self._process.poll() is None

    def endpoint(self) -> str:
        """Return probe endpoint URL from current config."""
        host = (self.index_manager.config.mcp_host or "127.0.0.1").strip()
        port = int(self.index_manager.config.mcp_port or 8765)
        return f"http://{host}:{port}/api/mcp-probe"

    def _build_command(self) -> list[str]:
        """Build command line for MCP subprocess launch."""
        config = self.index_manager.config
        repo_root = str(Path(config.project_root or Path.cwd()).resolve())
        output_dir = str(config.output_dir or "build")
        args = [
            sys.executable,
            "-m",
            "app.models.librarian_mcp_server",
            "--repo-root",
            repo_root,
            "--output-dir",
            output_dir,
            "--host",
            str(config.mcp_host or "127.0.0.1"),
            "--port",
            str(int(config.mcp_port or 8765)),
        ]
        if config.mcp_auth_token.strip():
            args.extend(["--token", config.mcp_auth_token.strip()])
        return args

    def start(self) -> tuple[bool, str]:
        """Start MCP subprocess if not already running."""
        if self.is_running():
            return False, "MCP server is already running."
        command = self._build_command()
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        app_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        if pythonpath:
            env["PYTHONPATH"] = f"{app_root}{os.pathsep}{pythonpath}"
        else:
            env["PYTHONPATH"] = str(app_root)

        try:
            self._process = subprocess.Popen(  # noqa: S603 - controlled local command
                command,
                cwd=str(app_root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=creationflags,
            )
        except OSError as exc:
            self._process = None
            return False, f"Failed to start MCP server: {exc}"
        return True, f"MCP server started at {self.endpoint()}"

    def stop(self) -> tuple[bool, str]:
        """Stop MCP subprocess if currently running."""
        if not self.is_running():
            return False, "MCP server is not running."
        assert self._process is not None
        self._process.terminate()
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)
        self._process = None
        return True, "MCP server stopped."
