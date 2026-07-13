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

"""Smoke tests for controller seam behavior."""

from __future__ import annotations

from pathlib import Path

from app.controllers.anti_pattern_controller import AntiPatternController
from app.controllers.main_window_controller import MainWindowViewController
from app.controllers.search_controller import SearchController
from app.indexer.index_manager import IndexManager


def test_search_controller_open_external_editor_delegates_to_model(monkeypatch, app_config, tmp_path):
    manager = IndexManager(app_config)
    controller = SearchController(index_manager=manager)
    target = tmp_path / "sample.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    monkeypatch.setattr(controller._path_controller, "resolve_path", lambda _path: target)

    called: dict[str, object] = {}

    def fake_launch_editor(file_path: Path, line_number: int | None, _config) -> bool:
        called["file"] = file_path
        called["line"] = line_number
        return True

    monkeypatch.setattr("app.controllers.search_controller.launch_editor", fake_launch_editor)

    assert controller.open_external_editor("sample.py", 7)
    assert called["file"] == target
    assert called["line"] == 7


def test_anti_pattern_controller_open_external_editor_delegates_to_model(monkeypatch, app_config, tmp_path):
    manager = IndexManager(app_config)
    controller = AntiPatternController(index_manager=manager)
    target = tmp_path / "module.py"
    target.write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(controller, "resolve_result_path", lambda _path: target)

    called: dict[str, object] = {}

    def fake_launch_editor(file_path: Path, line_number: int | None, _config) -> bool:
        called["file"] = file_path
        called["line"] = line_number
        return True

    monkeypatch.setattr("app.controllers.anti_pattern_controller.launch_editor", fake_launch_editor)

    assert controller.open_external_editor("module.py", 3)
    assert called["file"] == target
    assert called["line"] == 3


def test_main_window_controller_synchronize_root_restarts_running_mcp(app_config):
    manager = IndexManager(app_config)
    controller = MainWindowViewController(index_manager=manager)

    class FakeMCP:
        def __init__(self) -> None:
            self.stop_calls = 0
            self.start_calls = 0

        def is_running(self) -> bool:
            return True

        def stop(self) -> None:
            self.stop_calls += 1

        def start(self) -> tuple[bool, str]:
            self.start_calls += 1
            return True, "ok"

    fake_mcp = FakeMCP()
    normalized, status = controller.synchronize_project_root(str(Path.cwd()), fake_mcp)

    assert status == "MCP restarted for updated root"
    assert fake_mcp.stop_calls == 1
    assert fake_mcp.start_calls == 1
    assert manager.config.project_root == normalized


def test_main_window_controller_synchronize_root_skips_stopped_mcp(app_config):
    manager = IndexManager(app_config)
    controller = MainWindowViewController(index_manager=manager)

    class FakeMCP:
        def is_running(self) -> bool:
            return False

        def stop(self) -> None:  # pragma: no cover - defensive guard
            raise AssertionError("stop should not be called")

        def start(self) -> tuple[bool, str]:  # pragma: no cover - defensive guard
            raise AssertionError("start should not be called")

    normalized, status = controller.synchronize_project_root(str(Path.cwd()), FakeMCP())
    assert status is None
    assert manager.config.project_root == normalized
