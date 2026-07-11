# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#

"""Smoke tests for the editor launcher logic."""

from __future__ import annotations

from pathlib import Path
from app.config import AppConfig
from app.services.editor_launcher import launch_editor


def test_launch_editor_custom_cmd(monkeypatch, tmp_path):
    config = AppConfig(external_editor_cmd="mock_editor -open {file} -line {line}")

    called_cmd = []

    def mock_popen(cmd, *args, **kwargs):
        called_cmd.append(cmd)
        # return a mock process object
        class MockProcess:
            pass
        return MockProcess()

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    test_file = tmp_path / "test.py"
    test_file.touch()

    res = launch_editor(test_file, 42, config)
    assert res is True
    assert len(called_cmd) == 1
    assert "mock_editor -open" in called_cmd[0]
    assert "test.py" in called_cmd[0]
    assert "42" in called_cmd[0]


def test_launch_editor_fallback_not_found(monkeypatch, tmp_path):
    config = AppConfig(external_editor_cmd="")

    # Mock shutil.which to find nothing
    monkeypatch.setattr("shutil.which", lambda name: None)

    test_file = tmp_path / "test.py"
    test_file.touch()

    res = launch_editor(test_file, 10, config)
    assert res is False
