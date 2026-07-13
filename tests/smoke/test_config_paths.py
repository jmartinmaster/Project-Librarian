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

"""Smoke tests for platform-aware config directory resolution."""

from __future__ import annotations

from pathlib import Path

import app.config as config_module


def test_default_config_dir_uses_localappdata_on_windows(monkeypatch):
    monkeypatch.setattr(config_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")

    config_dir = config_module._default_config_dir()
    assert config_dir == Path(r"C:\Users\tester\AppData\Local") / "The Librarian"


def test_default_output_dir_uses_localappdata_on_windows(monkeypatch):
    monkeypatch.setattr(config_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")

    output_dir = config_module._default_output_dir()
    expected = (Path(r"C:\Users\tester\AppData\Local") / "The Librarian" / "build").resolve()
    assert Path(output_dir) == expected


def test_config_roundtrip_includes_integration_and_mcp_fields(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config = config_module.AppConfig(
        project_root="C:/repo",
        mvc_editor_root="C:/tools/MVC_editor",
        mcp_host="127.0.0.1",
        mcp_port=8877,
        mcp_auth_token="abc123",
        mcp_transport="streamable-http",
        mcp_autostart=True,
    )
    config_module.save_config(config, config_path=config_path)
    loaded = config_module.load_config(config_path=config_path)

    assert loaded.mvc_editor_root == "C:/tools/MVC_editor"
    assert loaded.mcp_host == "127.0.0.1"
    assert loaded.mcp_port == 8877
    assert loaded.mcp_auth_token == "abc123"
    assert loaded.mcp_transport == "streamable-http"
    assert loaded.mcp_autostart is True
