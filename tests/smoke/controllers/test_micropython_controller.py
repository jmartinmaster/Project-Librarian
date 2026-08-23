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
"""Smoke tests for MicroPythonController."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.config import AppConfig
from app.controllers.micropython_controller import MicroPythonController


def test_micropython_controller_live_code_toggle():
    config = AppConfig(micropython_live_code=False)
    controller = MicroPythonController(config)

    assert controller.is_live_code_enabled() is False
    controller.set_live_code_enabled(True)
    assert controller.is_live_code_enabled() is True
    assert config.micropython_live_code is True


def test_micropython_controller_format_device_info():
    info = {
        "platform": "esp32",
        "uname": "Generic ESP32 module",
        "release": "1.23.0",
        "version": "v1.23.0 on 2024-06-02",
        "mem_free": "112340",
        "mem_alloc": "45200",
    }
    formatted = MicroPythonController.format_device_info(info)
    assert "Platform:      esp32" in formatted
    assert "Free RAM:      112340 bytes" in formatted

    error_formatted = MicroPythonController.format_device_info({"error": "Device timed out"})
    assert "Device Query Failed" in error_formatted


def test_micropython_controller_delegation(tmp_path):
    mock_runner = MagicMock()
    mock_runner.list_serial_ports.return_value = [{"port": "/dev/ttyACM0", "description": "Pico"}]
    mock_runner.run_file.return_value = (True, "output")
    mock_runner.upload_file.return_value = (True, "uploaded")
    mock_runner.soft_reset.return_value = (True, "reset")

    config = AppConfig()
    controller = MicroPythonController(config, runner=mock_runner)

    ports = controller.list_ports()
    assert len(ports) == 1
    assert ports[0]["port"] == "/dev/ttyACM0"

    ok, out = controller.run_file("test.py")
    assert ok is True
    assert out == "output"

    ok_up, msg_up = controller.upload_file("main.py")
    assert ok_up is True

    ok_res, msg_res = controller.soft_reset()
    assert ok_res is True

    mock_runner.is_permission_error.return_value = True
    assert controller.is_permission_error("PermissionError") is True

    mock_runner.fix_port_permissions.return_value = (True, "fixed")
    ok_fix, msg_fix = controller.fix_port_permissions("/dev/ttyACM0", "pass")
    assert ok_fix is True
    assert msg_fix == "fixed"

    mock_runner.run_command_with_sudo.return_value = (True, "sudo ok")
    ok_sudo, out_sudo = controller.run_with_sudo(["run", "main.py"], "pass", "/dev/ttyACM0")
    assert ok_sudo is True
    assert out_sudo == "sudo ok"

    mock_runner.send_repl_input.return_value = True
    assert controller.send_repl_input("test") is True

    mock_runner.list_device_files.return_value = (True, [{"name": "boot.py", "size": 120, "is_dir": False}])
    ok_ls, items = controller.list_device_files("/")
    assert ok_ls is True
    assert len(items) == 1
    assert items[0]["name"] == "boot.py"

    mock_runner.download_file.return_value = (True, "Downloaded")
    ok_dl, msg_dl = controller.download_file("boot.py", tmp_path / "boot.py")
    assert ok_dl is True

    mock_runner.delete_file.return_value = (True, "Deleted")
    ok_del, msg_del = controller.delete_device_file("temp.py")
    assert ok_del is True

