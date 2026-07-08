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

"""Memory profiling and leak testing service."""

from __future__ import annotations

import gc
import sys
import os
import json
import threading
import time
import signal
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QProcess
from PyQt6.QtWidgets import QApplication, QTabWidget


class DiagnosticsRunner(QObject):
    """QProcess wrapper to run headless profiling and capture merged streams line-by-line."""
    output_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(int, dict)
    profiling_completed = pyqtSignal(dict)
    live_snapshot_taken = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._handle_output)
        self.process.finished.connect(self._handle_finished)
        self.process.errorOccurred.connect(self._handle_error)
        self._last_result = {}
        self.temp_runner_path = None
        
    def start_profile(self, target_path: str | None = None, duration: int = 0, interval: int = 0, headless: bool = False) -> None:
        """Start the profiling process."""
        self._last_result = {}
        self.temp_runner_path = None
        
        cmd = sys.executable
        args = []
        
        main_path = str(Path(__file__).resolve().parent.parent.parent / "main.py")
        
        # If target path is provided, detect if there is a local virtual environment (.venv / venv)
        target_python = None
        if target_path:
            target_dir = Path(target_path).resolve().parent
            for search_dir in (target_dir, target_dir.parent):
                for venv_name in (".venv", "venv"):
                    venv_dir = search_dir / venv_name
                    if venv_dir.is_dir():
                        if sys.platform == "win32":
                            bin_path = venv_dir / "Scripts" / "python.exe"
                        else:
                            bin_path = venv_dir / "bin" / "python"
                            
                        if bin_path.is_file():
                            target_python = str(bin_path)
                            break
                if target_python:
                    break

        if target_path:
            if target_python:
                cmd = target_python
                self.output_received.emit(f"[Profiler] Detected target environment. Running using: {cmd}")
            else:
                self.output_received.emit(f"[Profiler] No local environment detected. Falling back to system: {cmd}")
            
            # Write a temporary runner file to ensure standard libraries are fully available
            # and to avoid any namespace collisions with Project Librarian's top-level imports.
            self.temp_runner_path = str(Path(target_path).resolve().parent / "_librarian_temp_profiler.py")
            
            # Escape paths for raw string inclusion in script template
            target_path_escaped = str(Path(target_path).resolve()).replace("\\", "\\\\")
            
            if target_path.lower().endswith(".exe"):
                runner_code = f"""import sys
import os
import json
import time
import subprocess
import ctypes
from ctypes import wintypes
from datetime import datetime

target_exe = r"{target_path_escaped}"
analyze_duration = {duration}
analyze_interval = {interval}

# Process Memory Counters
class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

def get_memory_bytes(pid):
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return 0
        try:
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(counters)
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
                return counters.WorkingSetSize
            return 0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return 0

print(f"Executing target executable (Duration: {{analyze_duration}}s)...")
sys.stdout.flush()

try:
    process = subprocess.Popen([target_exe])
    pid = process.pid
    
    # Wait a moment for process to initialize
    time.sleep(2)
    baseline_bytes = get_memory_bytes(pid)
    
    elapsed = 0
    if analyze_interval > 0:
        while (analyze_duration == 0 or elapsed < analyze_duration) and process.poll() is None:
            sleep_time = min(analyze_interval, analyze_duration - elapsed) if analyze_duration > 0 else analyze_interval
            time.sleep(sleep_time)
            elapsed += sleep_time
            
            if process.poll() is None or elapsed >= analyze_duration:
                live_kb = round(get_memory_bytes(pid) / 1024, 2)
                live_payload = {{
                    "__profile_snapshot__": True,
                    "name": f"snapshot_{{datetime.now().strftime('%Y%m%d_%H%M%S')}}",
                    "size_kb": live_kb
                }}
                print(json.dumps(live_payload))
                sys.stdout.flush()
    else:
        if analyze_duration > 0:
            time.sleep(analyze_duration)
        else:
            process.wait()
            
    print("Execution period finished. Taking final snapshot...")
    sys.stdout.flush()
    
    final_bytes = get_memory_bytes(pid)
    
    total_after_kb = round(final_bytes / 1024, 2)
    total_before_kb = round(baseline_bytes / 1024, 2)
    
    result = {{
        "__profile_result__": True,
        "cycles_run": 1,
        "total_allocated_before_kb": total_before_kb,
        "total_allocated_after_kb": total_after_kb,
        "size_growth_kb": round(total_after_kb - total_before_kb, 2),
        "top_differences": [],
    }}
    
    print(json.dumps(result))
    sys.stdout.flush()
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except Exception:
            process.kill()
except Exception as e:
    import traceback
    script_error = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    result = {{
        "__profile_result__": True,
        "cycles_run": 1,
        "total_allocated_before_kb": 0,
        "total_allocated_after_kb": 0,
        "size_growth_kb": 0,
        "top_differences": [],
        "error": script_error
    }}
    print(f"Executable execution error:\\n{{script_error}}", file=sys.stderr)
    print(json.dumps(result))
    sys.stdout.flush()
"""
            else:
                runner_code = f"""import sys
import os
import gc
import json
import runpy
import tracemalloc
import threading
import time
from pathlib import Path
from datetime import datetime

target_script_to_analyze = r"{target_path_escaped}"
analyze_duration = {duration}
analyze_interval = {interval}

tracemalloc.start(25)
script_error = None

for _ in range(3):
    gc.collect()
baseline = tracemalloc.take_snapshot()

print(f"Executing target script (Duration: {{analyze_duration}}s)...")
sys.stdout.flush()

def run_target():
    global script_error
    try:
        script_dir = str(Path(target_script_to_analyze).resolve().parent)
        
        # Prevent shadowing app folder
        project_root = r"{str(Path(__file__).resolve().parent.parent.parent).replace('\\', '\\\\')}"
        sys.path = [p for p in sys.path if str(Path(p).resolve()) != project_root]
        
        for mod_name in list(sys.modules.keys()):
            if mod_name == "app" or mod_name.startswith("app."):
                del sys.modules[mod_name]
                
        sys.path.insert(0, script_dir)
        runpy.run_path(target_script_to_analyze, run_name="__main__")
    except Exception as e:
        import traceback
        script_error = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(f"Script execution error:\\n{{script_error}}", file=sys.stderr)
        sys.stderr.flush()

target_thread = threading.Thread(target=run_target, daemon=True)
target_thread.start()

if analyze_interval > 0:
    elapsed = 0
    while (analyze_duration == 0 or elapsed < analyze_duration) and target_thread.is_alive():
        sleep_time = min(analyze_interval, analyze_duration - elapsed) if analyze_duration > 0 else analyze_interval
        target_thread.join(timeout=sleep_time)
        elapsed += sleep_time
        
        if target_thread.is_alive() or elapsed >= analyze_duration:
            for _ in range(3):
                gc.collect()
            live_snap = tracemalloc.take_snapshot()
            live_kb = round(sum(s.size for s in live_snap.statistics("lineno")) / 1024, 2)
            
            live_payload = {{
                "__profile_snapshot__": True,
                "name": f"snapshot_{{datetime.now().strftime('%Y%m%d_%H%M%S')}}",
                "size_kb": live_kb
            }}
            print(json.dumps(live_payload))
            sys.stdout.flush()
else:
    if analyze_duration > 0:
        target_thread.join(timeout=analyze_duration)
    else:
        target_thread.join()
    
print("Execution period finished. Taking final snapshot...")
sys.stdout.flush()

for _ in range(3):
    gc.collect()
    
current = tracemalloc.take_snapshot()
stats = current.compare_to(baseline, "lineno")

top_differences = []
for s in stats[:20]:
    if s.size_diff > 0:
        top_differences.append({{
            "size_diff_kb": round(s.size_diff / 1024, 2),
            "size_kb": round(s.size / 1024, 2),
            "count_diff": s.count_diff,
            "count": s.count,
            "traceback": [str(frame) for frame in s.traceback],
        }})

total_after_kb = round(sum(s.size for s in current.statistics("lineno")) / 1024, 2)
total_before_kb = round(sum(s.size for s in baseline.statistics("lineno")) / 1024, 2)

result = {{
    "__profile_result__": True,
    "cycles_run": 1,
    "total_allocated_before_kb": total_before_kb,
    "total_allocated_after_kb": total_after_kb,
    "size_growth_kb": round(total_after_kb - total_before_kb, 2),
    "top_differences": top_differences,
}}

if script_error:
    result["error"] = script_error

print(json.dumps(result))
sys.stdout.flush()
"""
            try:
                with open(self.temp_runner_path, "w", encoding="utf-8") as f:
                    f.write(runner_code)
            except Exception as e:
                self.output_received.emit(f"[Profiler] Failed to write temporary runner: {e}")
                self.temp_runner_path = None
                
            if self.temp_runner_path:
                args = [self.temp_runner_path]
                if headless:
                    args.append("--analyze-headless")
            else:
                args = [main_path, "--analyze", target_path, "--analyze-duration", str(duration)]
                if interval > 0:
                    args.extend(["--analyze-interval", str(interval)])
                if headless:
                    args.append("--analyze-headless")
        else:
            args = [main_path, "--internal-profile-run"]

        self.output_received.emit(f"Starting process: {cmd} {' '.join(args)}")
        self.process.start(cmd, args)

    def _handle_output(self) -> None:
        output = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # Check if line is a JSON payload
            if line.startswith("{"):
                if "__profile_snapshot__" in line:
                    try:
                        data = json.loads(line)
                        if isinstance(data, dict):
                            self.live_snapshot_taken.emit(data)
                            continue
                    except json.JSONDecodeError:
                        pass
                elif "__profile_result__" in line:
                    try:
                        data = json.loads(line)
                        if isinstance(data, dict):
                            self._last_result = data
                            self.profiling_completed.emit(data)
                            continue
                    except json.JSONDecodeError:
                        pass
                
            self.output_received.emit(line)
            
    def _handle_finished(self, exit_code, exit_status) -> None:
        self._cleanup_temp_runner()
        self.finished.emit(exit_code, self._last_result)
        
    def _handle_error(self, error) -> None:
        self._cleanup_temp_runner()
        self.error_occurred.emit(self.process.errorString())
        
    def kill(self) -> None:
        """Kill the underlying background process and all its children."""
        self._cleanup_temp_runner()
        pid = self.process.processId()
        if pid:
            if sys.platform == "win32":
                import subprocess

                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    self.process.terminate()
        self.process.kill()
        self.process.waitForFinished(1000)

    def _cleanup_temp_runner(self) -> None:
        if self.temp_runner_path:
            try:
                if os.path.exists(self.temp_runner_path):
                    os.remove(self.temp_runner_path)
            except Exception:
                pass
            self.temp_runner_path = None


class DiagnosticsService:
    """Service to handle memory allocations tracing and UI tab-switching leak tests."""

    def __init__(self) -> None:
        self._tracemalloc_snapshots = {}

    def profile_memory_payload(
        self,
        action: str,
        snapshot_name: str | None = None,
        other_snapshot_name: str | None = None,
        key_type: str = "lineno",
        limit: int = 20,
        n_frames: int = 10,
    ) -> dict:
        """Process a memory profiling action request using Python's tracemalloc."""
        import tracemalloc

        normalized_action = action.strip().lower()
        is_tracing = tracemalloc.is_tracing()

        if normalized_action == "start":
            if is_tracing:
                return {"ok": True, "message": f"Memory profiling is already active (tracing {n_frames} frames)."}
            tracemalloc.start(n_frames)
            return {"ok": True, "message": f"Memory profiling started successfully (tracing {n_frames} frames)."}

        elif normalized_action == "stop":
            if not is_tracing:
                return {"ok": True, "message": "Memory profiling is not active."}
            tracemalloc.stop()
            self._tracemalloc_snapshots.clear()
            return {"ok": True, "message": "Memory profiling stopped, all saved snapshots cleared."}

        elif normalized_action == "status":
            snapshots_list = list(self._tracemalloc_snapshots.keys())
            return {
                "active": is_tracing,
                "saved_snapshots_count": len(snapshots_list),
                "saved_snapshots": snapshots_list,
                "message": "Tracing is active." if is_tracing else "Tracing is inactive.",
            }

        elif normalized_action == "take_snapshot":
            if not is_tracing:
                tracemalloc.start(n_frames)
            snapshot = tracemalloc.take_snapshot()
            name = snapshot_name or f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            self._tracemalloc_snapshots[name] = snapshot

            stats = snapshot.statistics(key_type)
            return {
                "ok": True,
                "snapshot_name": name,
                "total_allocated_kb": round(sum(s.size for s in stats) / 1024, 2),
                "top_allocations": [
                    {"size_kb": round(s.size / 1024, 2), "count": s.count, "traceback": str(s.traceback)}
                    for s in stats[:limit]
                ],
            }

        elif normalized_action == "get_stats":
            if not self._tracemalloc_snapshots:
                return {"ok": False, "error": "No saved snapshots found. Take a snapshot first."}
            name = snapshot_name or list(self._tracemalloc_snapshots.keys())[-1]
            snapshot = self._tracemalloc_snapshots.get(name)
            if not snapshot:
                return {"ok": False, "error": f"Snapshot '{name}' not found."}
            stats = snapshot.statistics(key_type)
            return {
                "snapshot_name": name,
                "total_allocated_kb": round(sum(s.size for s in stats) / 1024, 2),
                "top_allocations": [
                    {"size_kb": round(s.size / 1024, 2), "count": s.count, "traceback": str(s.traceback)}
                    for s in stats[:limit]
                ],
            }

        elif normalized_action == "compare":
            if not self._tracemalloc_snapshots:
                return {"ok": False, "error": "No snapshots saved yet."}
            if not snapshot_name or not other_snapshot_name:
                return {"ok": False, "error": "Both snapshot_name and other_snapshot_name are required."}
            snap1 = self._tracemalloc_snapshots.get(snapshot_name)
            snap2 = self._tracemalloc_snapshots.get(other_snapshot_name)
            if not snap1:
                return {"ok": False, "error": f"Snapshot '{snapshot_name}' not found."}
            if not snap2:
                return {"ok": False, "error": f"Snapshot '{other_snapshot_name}' not found."}
            stats = snap2.compare_to(snap1, key_type)
            return {
                "comparison": f"Comparing '{other_snapshot_name}' (new) to '{snapshot_name}' (old)",
                "top_differences": [
                    {
                        "size_diff_kb": round(s.size_diff / 1024, 2),
                        "size_kb": round(s.size / 1024, 2),
                        "count_diff": s.count_diff,
                        "count": s.count,
                        "traceback": str(s.traceback),
                    }
                    for s in stats[:limit]
                ],
            }

        elif normalized_action == "clear":
            self._tracemalloc_snapshots.clear()
            return {"ok": True, "message": "All saved snapshots cleared."}

        return {"ok": False, "error": f"Unknown action '{action}'"}

    def run_subprocess_profile(self, target_path: str | None = None, duration: int = 0, interval: int = 0, headless: bool = False) -> DiagnosticsRunner:
        """Spawn a sandboxed subprocess for memory profiling instead of a crash-prone thread."""
        runner = DiagnosticsRunner()
        # Keep a reference to prevent garbage collection if the caller doesn't store it
        self._active_runner = runner 
        runner.start_profile(target_path, duration=duration, interval=interval, headless=headless)
        return runner
