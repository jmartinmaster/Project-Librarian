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
"""Device execution and REPL streaming runner for MicroPython hardware."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable


class MicroPythonRunner:
    """Service to communicate with, upload to, and debug MicroPython devices."""

    def __init__(self, runner_cmd: str = "mpremote", default_port: str = "auto", baud_rate: int = 115200) -> None:
        self.runner_cmd = runner_cmd or "mpremote"
        self.default_port = default_port or "auto"
        self.baud_rate = baud_rate
        self._active_repl_process: subprocess.Popen[str] | None = None
        self._repl_stop_event = threading.Event()
        self._repl_thread: threading.Thread | None = None

    @staticmethod
    def list_serial_ports() -> list[dict[str, str]]:
        """Detect connected serial and USB ports across platforms."""
        ports: list[dict[str, str]] = []

        if sys.platform.startswith("linux"):
            # Search Linux USB/ACM device nodes
            dev_nodes = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
            for node in dev_nodes:
                ports.append({"port": node, "description": f"Microcontroller Serial ({node})"})
        elif sys.platform == "darwin":
            dev_nodes = sorted(glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/tty.usbserial*"))
            for node in dev_nodes:
                ports.append({"port": node, "description": f"USB Serial Device ({node})"})
        elif sys.platform == "win32":
            # Check COM1 - COM32 on Windows
            for i in range(1, 33):
                port_name = f"COM{i}"
                ports.append({"port": port_name, "description": f"Serial Port ({port_name})"})

        if not ports:
            ports.append({"port": "auto", "description": "Auto-detect (Default)"})

        return ports

    def _resolve_command_prefix(self, port: str | None = None) -> list[str]:
        """Build the executable command list for mpremote / device runner."""
        selected_port = (port or self.default_port).strip()
        cmd = self.runner_cmd.strip() or "mpremote"

        # Check if runner command exists in PATH or active python environment
        exe = shutil.which(cmd)
        if exe is None:
            # Check if runner exists as module in sys.executable (e.g. python -m mpremote)
            prefix = [sys.executable, "-m", cmd]
        else:
            prefix = [exe]

        if selected_port and selected_port.lower() != "auto":
            prefix.extend(["connect", selected_port])

        return prefix

    def _run_command(self, args: list[str], timeout_seconds: float = 15.0) -> tuple[bool, str]:
        """Run a runner sub-command synchronously and capture output."""
        cmd = [*self._resolve_command_prefix(), *args]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            combined = (stdout + ("\n" + stderr if stderr else "")).strip()
            return completed.returncode == 0, combined or (stdout.strip() or stderr.strip())
        except subprocess.TimeoutExpired:
            return False, f"Error: Command timed out after {timeout_seconds} seconds."
        except Exception as exc:
            return False, f"Execution error: {exc.__class__.__name__}: {exc}"

    def get_device_info(self, port: str | None = None) -> tuple[bool, dict[str, str]]:
        """Query connected MicroPython device for platform, release, and heap memory."""
        info_code = (
            "import sys, gc, os; "
            "gc.collect(); "
            "uname = getattr(os, 'uname', lambda: [''])(); "
            "print('---DEVICE_INFO_START---'); "
            "print('platform:', sys.platform); "
            "print('version:', getattr(sys, 'version', 'unknown')); "
            "print('uname:', getattr(uname, 'sysname', str(uname))); "
            "print('release:', getattr(uname, 'release', 'unknown')); "
            "print('mem_free:', gc.mem_free()); "
            "print('mem_alloc:', gc.mem_alloc()); "
            "print('---DEVICE_INFO_END---')"
        )
        cmd_prefix = self._resolve_command_prefix(port)
        cmd = [*cmd_prefix, "exec", info_code]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=8.0, check=False)
            output = (completed.stdout or "").strip()
            if completed.returncode != 0 or "---DEVICE_INFO_START---" not in output:
                return False, {"error": completed.stderr or output or "Unable to retrieve device info."}

            extracted: dict[str, str] = {}
            recording = False
            for line in output.splitlines():
                if "---DEVICE_INFO_START---" in line:
                    recording = True
                    continue
                if "---DEVICE_INFO_END---" in line:
                    break
                if recording and ":" in line:
                    key, val = line.split(":", 1)
                    extracted[key.strip()] = val.strip()

            return True, extracted
        except Exception as exc:
            return False, {"error": f"{exc.__class__.__name__}: {exc}"}

    def run_file(self, local_path: str | Path, port: str | None = None) -> tuple[bool, str]:
        """Execute a local Python script on the device."""
        path_obj = Path(local_path)
        if not path_obj.exists():
            return False, f"Local file not found: {local_path}"

        cmd = [*self._resolve_command_prefix(port), "run", str(path_obj.resolve())]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0, check=False)
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            combined = (stdout + ("\n" + stderr if stderr else "")).strip()
            return completed.returncode == 0, combined
        except Exception as exc:
            return False, f"Run error: {exc.__class__.__name__}: {exc}"

    def exec_code(self, code_str: str, port: str | None = None) -> tuple[bool, str]:
        """Execute Python code string directly on the device."""
        cmd = [*self._resolve_command_prefix(port), "exec", code_str]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0, check=False)
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            return completed.returncode == 0, (stdout + ("\n" + stderr if stderr else "")).strip()
        except Exception as exc:
            return False, f"Exec error: {exc.__class__.__name__}: {exc}"

    def upload_file(
        self,
        local_path: str | Path,
        remote_path: str = "main.py",
        port: str | None = None,
    ) -> tuple[bool, str]:
        """Upload a local file to the device flash filesystem."""
        path_obj = Path(local_path)
        if not path_obj.exists():
            return False, f"Local file not found: {local_path}"

        target = remote_path if remote_path.startswith(":") else f":{remote_path.lstrip('/')}"
        cmd = [*self._resolve_command_prefix(port), "fs", "cp", str(path_obj.resolve()), target]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=20.0, check=False)
            if completed.returncode == 0:
                return True, f"Successfully uploaded {path_obj.name} to device ({target})"
            return False, completed.stderr or completed.stdout or "Upload failed."
        except Exception as exc:
            return False, f"Upload error: {exc.__class__.__name__}: {exc}"

    def list_device_files(self, remote_dir: str = "/", port: str | None = None) -> tuple[bool, list[dict[str, Any]]]:
        """List files and directories stored on microcontroller."""
        import json
        clean_dir = remote_dir.strip() or "/"
        py_code = (
            f"import os, json; "
            f"d = '{clean_dir}'; "
            f"def _l(path): "
            f"    try: "
            f"        res = []; "
            f"        for item in os.listdir(path): "
            f"            full = (path + '/' + item).replace('//', '/'); "
            f"            st = os.stat(full); "
            f"            is_dir = bool(st[0] & 0x4000); "
            f"            size = st[6] if not is_dir else 0; "
            f"            res.append({{'name': item, 'path': full, 'is_dir': is_dir, 'size': size}}); "
            f"        return res; "
            f"    except: return []; "
            f"print('---FS_LIST_START---'); "
            f"print(json.dumps(_l(d))); "
            f"print('---FS_LIST_END---')"
        )
        ok, out = self.exec_code(py_code, port=port)
        if not ok or "---FS_LIST_START---" not in out:
            return False, []

        try:
            raw_json = out.split("---FS_LIST_START---")[1].split("---FS_LIST_END---")[0].strip()
            items = json.loads(raw_json)
            return True, items
        except Exception:
            return False, []

    def download_file(
        self,
        remote_path: str,
        local_path: str | Path,
        port: str | None = None,
    ) -> tuple[bool, str]:
        """Download a file from microcontroller to local disk."""
        target = remote_path if remote_path.startswith(":") else f":{remote_path.lstrip('/')}"
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [*self._resolve_command_prefix(port), "fs", "cp", target, str(dest.resolve())]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=20.0, check=False)
            if completed.returncode == 0:
                return True, f"Downloaded {remote_path} to {dest.name}"
            return False, completed.stderr or completed.stdout or "Download failed."
        except Exception as exc:
            return False, f"Download error: {exc.__class__.__name__}: {exc}"

    def delete_file(self, remote_path: str, port: str | None = None) -> tuple[bool, str]:
        """Delete a file from microcontroller flash."""
        clean_path = remote_path.lstrip(":")
        py_code = f"import os; os.remove('{clean_path}')"
        ok, out = self.exec_code(py_code, port=port)
        if ok:
            return True, f"Deleted {clean_path} from device"
        return False, f"Failed to delete {clean_path}: {out}"

    def soft_reset(self, port: str | None = None) -> tuple[bool, str]:
        """Trigger a soft reset on the microcontroller."""
        cmd = [*self._resolve_command_prefix(port), "reset"]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=8.0, check=False)
            return completed.returncode == 0, completed.stdout or completed.stderr or "Soft reset triggered."
        except Exception as exc:
            return False, f"Reset error: {exc.__class__.__name__}: {exc}"

    def is_repl_active(self) -> bool:
        """Return True if a REPL watch stream is actively running."""
        return self._active_repl_process is not None and self._active_repl_process.poll() is None

    def stop_repl_monitor(self) -> None:
        """Stop active REPL streaming process."""
        self._repl_stop_event.set()
        proc = self._active_repl_process
        self._active_repl_process = None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def start_repl_monitor(
        self,
        port: str | None = None,
        on_output_line: Callable[[str], None] | None = None,
        on_finished: Callable[[int, str], None] | None = None,
    ) -> None:
        """Start streaming live REPL output in a background thread."""
        self.stop_repl_monitor()
        self._repl_stop_event.clear()

        def _monitor_loop() -> None:
            cmd = [*self._resolve_command_prefix(port), "repl"]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._active_repl_process = proc

                if on_output_line:
                    on_output_line("[REPL Monitor Connected. Watching device output...]\n")

                while not self._repl_stop_event.is_set():
                    if proc.poll() is not None:
                        break
                    line = proc.stdout.readline() if proc.stdout else ""
                    if line:
                        if on_output_line:
                            on_output_line(line)
                    else:
                        time.sleep(0.05)

                ret = proc.poll() or 0
                if on_finished:
                    on_finished(ret, "REPL monitoring session ended.")
            except Exception as exc:
                if on_output_line:
                    on_output_line(f"\n[REPL Error: {exc}]\n")
                if on_finished:
                    on_finished(1, str(exc))
            finally:
                self._active_repl_process = None

        self._repl_thread = threading.Thread(target=_monitor_loop, name="micropython-repl-stream", daemon=True)
        self._repl_thread.start()

    def upload_and_debug(
        self,
        local_path: str | Path,
        remote_path: str = "main.py",
        port: str | None = None,
        on_output_line: Callable[[str], None] | None = None,
        on_finished: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Upload & Debug Workflow:
        1. Upload the target file to the device filesystem.
        2. Soft-reset the device.
        3. Immediately stream REPL to capture the full startup / boot sequence.
        """
        if on_output_line:
            on_output_line(f"[Upload & Debug] Step 1: Uploading {Path(local_path).name} -> :{remote_path}...\n")

        ok, msg = self.upload_file(local_path, remote_path, port)
        if not ok:
            if on_output_line:
                on_output_line(f"[Upload Failed] {msg}\n")
            if on_finished:
                on_finished(1, msg)
            return

        if on_output_line:
            on_output_line(f"[Upload OK] {msg}\n[Upload & Debug] Step 2: Soft resetting device and attaching REPL...\n")

        # Soft reset and stream REPL
        self.soft_reset(port)
        time.sleep(0.3)
        self.start_repl_monitor(port=port, on_output_line=on_output_line, on_finished=on_finished)

    @staticmethod
    def is_permission_error(output: str) -> bool:
        """Return True if output text indicates a permission or access denied error."""
        if not output:
            return False
        normalized = output.lower()
        patterns = [
            "permission denied",
            "permissionerror",
            "errno 13",
            "access denied",
            "operation not permitted",
            "could not open port",
            "access is denied",
        ]
        return any(pat in normalized for pat in patterns)

    def fix_port_permissions(self, port: str, sudo_password: str) -> tuple[bool, str]:
        """Execute 'sudo -S chmod 666 <port>' to grant user read/write access to device port."""
        if not port or port.lower() == "auto":
            # Find default port nodes
            candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
            if not candidates:
                return False, "No serial device node found to chmod."
            port = candidates[0]

        cmd = ["sudo", "-S", "chmod", "666", port]
        try:
            completed = subprocess.run(
                cmd,
                input=f"{sudo_password}\n",
                capture_output=True,
                text=True,
                timeout=8.0,
                check=False,
            )
            if completed.returncode == 0:
                return True, f"Successfully updated permissions on {port} (chmod 666)."
            err = completed.stderr or completed.stdout or "Sudo authentication failed."
            return False, f"Failed to set permissions on {port}: {err.strip()}"
        except Exception as exc:
            return False, f"Sudo error: {exc.__class__.__name__}: {exc}"

    def run_command_with_sudo(
        self,
        args: list[str],
        sudo_password: str,
        port: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> tuple[bool, str]:
        """Execute runner command under sudo -S with password piped to stdin."""
        base_cmd = self._resolve_command_prefix(port)
        full_cmd = ["sudo", "-S", *base_cmd, *args]
        try:
            completed = subprocess.run(
                full_cmd,
                input=f"{sudo_password}\n",
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            combined = (stdout + ("\n" + stderr if stderr else "")).strip()
            return completed.returncode == 0, combined
        except Exception as exc:
            return False, f"Sudo command error: {exc.__class__.__name__}: {exc}"

    def send_repl_input(self, text: str) -> bool:
        """Send a line of text/command into the actively running REPL process."""
        proc = self._active_repl_process
        if proc is not None and proc.poll() is None and proc.stdin:
            try:
                proc.stdin.write(text if text.endswith("\n") else f"{text}\n")
                proc.stdin.flush()
                return True
            except Exception:
                return False
        return False
