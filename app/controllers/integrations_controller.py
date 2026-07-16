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
"""Controller for integration settings and MCP server lifecycle."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from app.config import AppConfig, save_config
from app.models.mcp_server_manager import MCPServerManager

DEFAULT_MVC_EDITOR_PATH = Path(r"C:\Users\jamie\OneDrive\Personel\Documents\GitHub\MVC_editor")


class IntegrationsController:
    """Delegates integrations actions and config updates."""

    def __init__(self, config: AppConfig, mcp_manager: MCPServerManager) -> None:
        self.config = config
        self.mcp_manager = mcp_manager

    def save_settings(
        self,
        new_root: str,
        host: str,
        port: int,
        token: str,
        autostart: bool,
        ai_url: str = "",
        ai_model: str = "",
        ai_boilerplate_only: bool = False,
    ) -> bool:
        """Save settings to config file.
        
        Returns:
            True if the project root changed, False otherwise.
        """
        previous_root = str(Path(self.config.project_root or Path.cwd()).resolve())
        self.config.project_root = new_root
        self.config.mvc_editor_root = new_root
        self.config.mcp_host = host or "127.0.0.1"
        self.config.mcp_port = port
        self.config.mcp_auth_token = token
        self.config.mcp_transport = "streamable-http"
        self.config.mcp_autostart = autostart
        self.config.ai_url = ai_url or "http://localhost:11434/api/generate"
        self.config.ai_model = ai_model or "qwen2.5-coder:14b"
        self.config.ai_boilerplate_only = ai_boilerplate_only
        save_config(self.config)
        
        return bool(new_root and new_root != previous_root)

    def is_mcp_running(self) -> bool:
        """Check if MCP server is running."""
        return self.mcp_manager.is_running()

    def mcp_endpoint(self) -> str:
        """Get the current MCP server endpoint."""
        return self.mcp_manager.endpoint()

    def start_mcp_server(self) -> tuple[bool, str]:
        """Start the MCP server."""
        return self.mcp_manager.start()

    def stop_mcp_server(self) -> tuple[bool, str]:
        """Stop the MCP server."""
        return self.mcp_manager.stop()

    def open_mvc_folder(self, root_path: str) -> tuple[bool, str]:
        """Open the provided folder path using the OS file manager."""
        path = Path(root_path.strip())
        if not path.exists():
            return False, "MVC Editor root does not exist."
            
        if sys.platform == "win32":
            subprocess.run(["explorer", str(path)], check=False, capture_output=True)  # noqa: S603
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, str(path)], check=False, capture_output=True)  # noqa: S603
        return True, ""

    def launch_mvc_editor(self) -> tuple[bool, str]:
        """Launch the external MVC editor."""
        path = Path((self.config.mvc_editor_root or "").strip())
        if not path:
            if DEFAULT_MVC_EDITOR_PATH.exists():
                path = DEFAULT_MVC_EDITOR_PATH
            else:
                return False, "External MVC editor path is not configured."
                
        entrypoint = path / "main.py"
        if not entrypoint.exists():
            return False, f"Could not find {entrypoint}."
            
        venv_python = path / ".venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        subprocess.Popen(  # noqa: S603 - local trusted command
            [python_exe, str(entrypoint)],
            cwd=str(Path(self.config.project_root or Path.cwd()).resolve()),
            creationflags=creationflags,
        )
        
        self.config.mvc_editor_root = str(path.resolve())
        save_config(self.config)
        return True, ""

    def probe_mcp_server(self, token: str) -> tuple[bool, str, dict | None]:
        """Probe the MCP endpoint.
        
        Returns:
            Tuple of (success, message, response_data)
        """
        endpoint = self.mcp_manager.endpoint()
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        request = urllib.request.Request(endpoint, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                status_code = int(getattr(response, "status", 200))
                response_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return False, f"Probe returned HTTP {exc.code}", None
        except urllib.error.URLError as exc:
            return False, f"Failed to connect to MCP server: {exc.reason}", None
        except TimeoutError:
            return False, "Probe request timed out.", None

        if status_code >= 400:
            return False, f"Probe returned HTTP {status_code}", None

        try:
            data = json.loads(response_body)
            return True, "Probe successful.", data
        except json.JSONDecodeError:
            return False, "Probe returned invalid JSON.", None
