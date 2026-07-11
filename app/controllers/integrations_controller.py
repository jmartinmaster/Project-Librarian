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

"""Controller for MCP server lifecycle and integrations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from app.config import AppConfig, save_config
from app.services.mcp_server_manager import MCPServerManager


class IntegrationsController:
    """Orchestrates MCP server controls and settings."""

    def __init__(
        self,
        config: AppConfig,
        mcp_manager: MCPServerManager,
        on_project_root_changed: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.mcp_manager = mcp_manager
        self._on_project_root_changed = on_project_root_changed

    def save_settings(self, host: str, port: int, token: str, transport: str, autostart: bool) -> None:
        """Persist integration settings to config file."""
        self.config.mcp_host = host or "127.0.0.1"
        self.config.mcp_port = port
        self.config.mcp_auth_token = token
        self.config.mcp_transport = transport or "streamable-http"
        self.config.mcp_autostart = autostart
        save_config(self.config)

    def start_mcp_server(self) -> tuple[bool, str]:
        """Start the MCP server."""
        return self.mcp_manager.start()

    def stop_mcp_server(self) -> tuple[bool, str]:
        """Stop the MCP server."""
        return self.mcp_manager.stop()

    def probe_mcp_server(self, token: str) -> tuple[bool, str]:
        """Probe MCP endpoint and return (success, status_message)."""
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
            return False, f"Probe returned HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return False, f"Could not reach MCP endpoint:\n{exc}"

        if status_code != 200:
            return False, f"Probe returned HTTP {status_code}"

        try:
            payload = json.loads(response_body)
        except ValueError:
            return False, "Probe returned non-JSON response."

        status_text = str(payload.get("status", "ok"))
        return True, status_text

    def _get_base_url(self) -> str:
        """Get base URL for MCP server."""
        host = (self.config.mcp_host or "127.0.0.1").strip()
        port = int(self.config.mcp_port or 8765)
        return f"http://{host}:{port}"

    def search_via_mcp(self, query: str, token: str) -> tuple[bool, dict[str, Any] | str]:
        """Query /api/search via MCP server."""
        import urllib.parse
        base_url = self._get_base_url()
        url = f"{base_url}/api/search?q={urllib.parse.quote(query)}"
        
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status_code = int(getattr(response, "status", 200))
                response_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return False, f"Search returned HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return False, f"Could not reach MCP server:\n{exc}"
            
        if status_code != 200:
            return False, f"Search returned HTTP {status_code}"
            
        try:
            payload = json.loads(response_body)
            return True, payload
        except ValueError:
            return False, "Search returned non-JSON response."

    def get_ast_via_mcp(self, file_path: str, token: str) -> tuple[bool, dict[str, Any] | str]:
        """Query /api/ast via MCP server."""
        import urllib.parse
        base_url = self._get_base_url()
        url = f"{base_url}/api/ast?path={urllib.parse.quote(file_path)}"
        
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status_code = int(getattr(response, "status", 200))
                response_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return False, f"AST query returned HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return False, f"Could not reach MCP server:\n{exc}"
            
        if status_code != 200:
            return False, f"AST query returned HTTP {status_code}"
            
        try:
            payload = json.loads(response_body)
            return True, payload
        except ValueError:
            return False, "AST query returned non-JSON response."

