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
"""Smoke tests for MicroPython runner service."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models.micropython_runner import MicroPythonRunner


def test_list_serial_ports():
    ports = MicroPythonRunner.list_serial_ports()
    assert isinstance(ports, list)
    assert len(ports) >= 1
    assert "port" in ports[0]
    assert "description" in ports[0]


def test_command_prefix_resolution():
    runner = MicroPythonRunner(runner_cmd="mpremote", default_port="/dev/ttyACM0")
    prefix = runner._resolve_command_prefix()
    assert "connect" in prefix
    assert "/dev/ttyACM0" in prefix

    runner_auto = MicroPythonRunner(runner_cmd="mpremote", default_port="auto")
    prefix_auto = runner_auto._resolve_command_prefix()
    assert "connect" not in prefix_auto


def test_get_device_info_parsing(monkeypatch):
    runner = MicroPythonRunner()
    fake_output = (
        "---DEVICE_INFO_START---\n"
        "platform: rp2\n"
        "version: 3.4.0\n"
        "uname: rp2\n"
        "release: 1.22.0\n"
        "mem_free: 184520\n"
        "mem_alloc: 12480\n"
        "---DEVICE_INFO_END---\n"
    )

    def mock_run(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = fake_output
        mock_proc.stderr = ""
        return mock_proc

    monkeypatch.setattr(subprocess, "run", mock_run)
    ok, info = runner.get_device_info()
    assert ok is True
    assert info["platform"] == "rp2"
    assert info["mem_free"] == "184520"
    assert info["mem_alloc"] == "12480"


def test_run_file_and_upload(tmp_path, monkeypatch):
    test_file = tmp_path / "blink.py"
    test_file.write_text("import machine; print('Hello MicroPython')", encoding="utf-8")

    runner = MicroPythonRunner()

    def mock_run(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Hello MicroPython\n"
        mock_proc.stderr = ""
        return mock_proc

    monkeypatch.setattr(subprocess, "run", mock_run)

    ok, output = runner.run_file(test_file)
    assert ok is True
    assert "Hello MicroPython" in output

    ok_up, msg_up = runner.upload_file(test_file, remote_path="main.py")
    assert ok_up is True
    assert "uploaded" in msg_up.lower()


def test_upload_and_debug_flow(tmp_path, monkeypatch):
    test_file = tmp_path / "main.py"
    test_file.write_text("print('Booting...')", encoding="utf-8")

    runner = MicroPythonRunner()
    logs: list[str] = []

    def mock_run(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "OK"
        mock_proc.stderr = ""
        return mock_proc

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(runner, "start_repl_monitor", lambda port, on_output_line, on_finished: logs.append("REPL_STARTED"))

    runner.upload_and_debug(
        local_path=test_file,
        remote_path="main.py",
        on_output_line=lambda text: logs.append(text),
    )

    assert any("Step 1: Uploading" in l for l in logs)
    assert any("Step 2: Soft resetting" in l for l in logs)
    assert "REPL_STARTED" in logs


def test_permission_error_detection():
    assert MicroPythonRunner.is_permission_error("PermissionError: [Errno 13] Permission denied: '/dev/ttyACM0'")
    assert MicroPythonRunner.is_permission_error("could not open port /dev/ttyUSB0: [Errno 13] Permission denied")
    assert MicroPythonRunner.is_permission_error("Access is denied.")
    assert not MicroPythonRunner.is_permission_error("SyntaxError: invalid syntax")
    assert not MicroPythonRunner.is_permission_error("")


def test_fix_port_permissions(monkeypatch):
    runner = MicroPythonRunner()

    def mock_run(cmd, *args, **kwargs):
        assert cmd[0] == "sudo"
        assert "chmod" in cmd
        assert "666" in cmd
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        return mock_proc

    monkeypatch.setattr(subprocess, "run", mock_run)
    ok, msg = runner.fix_port_permissions("/dev/ttyACM0", "testpass")
    assert ok is True
    assert "chmod 666" in msg


def test_run_command_with_sudo(monkeypatch):
    runner = MicroPythonRunner()

    def mock_run(cmd, *args, **kwargs):
        assert cmd[0] == "sudo"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Execution OK"
        mock_proc.stderr = ""
        return mock_proc

    monkeypatch.setattr(subprocess, "run", mock_run)
    ok, out = runner.run_command_with_sudo(["run", "main.py"], "testpass", port="/dev/ttyACM0")
    assert ok is True
    assert out == "Execution OK"


def test_send_repl_input():
    runner = MicroPythonRunner()
    # When no process is active, should return False safely
    assert runner.send_repl_input("print(1)\n") is False

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdin = MagicMock()
    runner._active_repl_process = mock_proc

    assert runner.send_repl_input("print(1)") is True
    mock_proc.stdin.write.assert_called_with("print(1)\n")
    mock_proc.stdin.flush.assert_called_once()
