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
"""MicroPython device workflow and hardware testing controller."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.config import AppConfig
from app.models.micropython_runner import MicroPythonRunner


class MicroPythonController:
    """Controller seam for MicroPython hardware interactions and live debugging."""

    def __init__(self, config: AppConfig, runner: MicroPythonRunner | None = None) -> None:
        self.config = config
        self.runner = runner or MicroPythonRunner(
            runner_cmd=getattr(config, "micropython_runner_cmd", "mpremote"),
            default_port=getattr(config, "micropython_port", "auto"),
            baud_rate=getattr(config, "micropython_baud", 115200),
        )

    def is_live_code_enabled(self) -> bool:
        """Return True if Live Code execution mode is enabled in config."""
        return bool(getattr(self.config, "micropython_live_code", False))

    def set_live_code_enabled(self, enabled: bool) -> None:
        """Set Live Code execution mode."""
        self.config.micropython_live_code = bool(enabled)

    def list_ports(self) -> list[dict[str, str]]:
        """List detected serial and USB ports."""
        return self.runner.list_serial_ports()

    def get_device_info(self, port: str | None = None) -> tuple[bool, dict[str, str]]:
        """Query device information from microcontroller."""
        return self.runner.get_device_info(port=port)

    def run_file(self, file_path: str | Path, port: str | None = None) -> tuple[bool, str]:
        """Execute a Python file directly on the microcontroller."""
        return self.runner.run_file(local_path=file_path, port=port)

    def exec_code(self, code_str: str, port: str | None = None) -> tuple[bool, str]:
        """Execute inline code string on the microcontroller."""
        return self.runner.exec_code(code_str=code_str, port=port)

    def upload_file(
        self,
        file_path: str | Path,
        remote_path: str = "main.py",
        port: str | None = None,
    ) -> tuple[bool, str]:
        """Upload a file to the device flash filesystem."""
        return self.runner.upload_file(local_path=file_path, remote_path=remote_path, port=port)

    def list_device_files(self, remote_dir: str = "/", port: str | None = None) -> tuple[bool, list[dict[str, Any]]]:
        """List files stored on the microcontroller."""
        return self.runner.list_device_files(remote_dir=remote_dir, port=port)

    def download_file(
        self,
        remote_path: str,
        local_path: str | Path,
        port: str | None = None,
    ) -> tuple[bool, str]:
        """Download a file from microcontroller to local disk."""
        return self.runner.download_file(remote_path=remote_path, local_path=local_path, port=port)

    def delete_device_file(self, remote_path: str, port: str | None = None) -> tuple[bool, str]:
        """Delete a file on the microcontroller flash."""
        return self.runner.delete_file(remote_path=remote_path, port=port)

    def soft_reset(self, port: str | None = None) -> tuple[bool, str]:
        """Send a soft reset command to the microcontroller."""
        return self.runner.soft_reset(port=port)

    def upload_and_debug(
        self,
        file_path: str | Path,
        remote_path: str = "main.py",
        port: str | None = None,
        on_output_line: Callable[[str], None] | None = None,
        on_finished: Callable[[int, str], None] | None = None,
    ) -> None:
        """Upload target file, soft reset the device, and monitor the boot sequence."""
        self.runner.upload_and_debug(
            local_path=file_path,
            remote_path=remote_path,
            port=port,
            on_output_line=on_output_line,
            on_finished=on_finished,
        )

    def start_repl(
        self,
        port: str | None = None,
        on_output_line: Callable[[str], None] | None = None,
        on_finished: Callable[[int, str], None] | None = None,
    ) -> None:
        """Start live REPL output monitoring."""
        self.runner.start_repl_monitor(port=port, on_output_line=on_output_line, on_finished=on_finished)

    def stop_repl(self) -> None:
        """Stop active live REPL output monitoring."""
        self.runner.stop_repl_monitor()

    def is_repl_active(self) -> bool:
        """Return True if REPL stream is actively running."""
        return self.runner.is_repl_active()

    def is_permission_error(self, output: str) -> bool:
        """Check if an error string represents a permission error."""
        return self.runner.is_permission_error(output)

    def fix_port_permissions(self, port: str, sudo_password: str) -> tuple[bool, str]:
        """Execute sudo chmod 666 on the port."""
        return self.runner.fix_port_permissions(port=port, sudo_password=sudo_password)

    def run_with_sudo(self, args: list[str], sudo_password: str, port: str | None = None) -> tuple[bool, str]:
        """Execute runner command under sudo."""
        return self.runner.run_command_with_sudo(args=args, sudo_password=sudo_password, port=port)

    def send_repl_input(self, text: str) -> bool:
        """Send input to live REPL process."""
        return self.runner.send_repl_input(text)

    @staticmethod
    def format_device_info(info: dict[str, str]) -> str:
        """Format raw device query dictionary into human-readable text."""
        if "error" in info:
            return f"Device Query Failed: {info['error']}"

        lines = [
            "--- MicroPython Device Information ---",
            f"Platform:      {info.get('platform', 'unknown')}",
            f"Sysname:       {info.get('uname', 'unknown')}",
            f"Release:       {info.get('release', 'unknown')}",
            f"Version:       {info.get('version', 'unknown')}",
            f"Free RAM:      {info.get('mem_free', '0')} bytes",
            f"Allocated RAM: {info.get('mem_alloc', '0')} bytes",
            "---------------------------------------",
        ]
        return "\n".join(lines)
