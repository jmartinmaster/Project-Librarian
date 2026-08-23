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
"""Diagnostics workflow controller skeleton."""

from __future__ import annotations

import csv
import re
import subprocess
import sys

from app.models.diagnostics_model import DiagnosticsModel
from app.models.micropython_model import is_micropython_module, get_micropython_module_info


class DiagnosticsController:
    """Controller seam for diagnostics orchestration behavior."""

    _MODULE_PACKAGE_MAPPING = {
        "PIL": "Pillow",
        "cv2": "opencv-python",
        "yaml": "PyYAML",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv",
    }

    def install_package(self, package_name: str) -> tuple[bool, str]:
        """Install a package using the active Python environment."""
        try:
            cmd = [sys.executable, "-m", "pip", "install", package_name]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            return True, result.stdout
        except subprocess.CalledProcessError as exc:
            return False, exc.stderr
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def export_comparison_to_csv(comparison_rows: list[dict[str, object]], file_path: str) -> None:
        """Export allocation comparison rows to CSV."""
        with open(file_path, "w", newline="", encoding="utf-8") as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow(["Diff Size (KB)", "Total Size (KB)", "Count Diff", "Location"])
            for diff in comparison_rows:
                writer.writerow(
                    [
                        diff.get("size_diff_kb", 0.0),
                        diff.get("size_kb", 0.0),
                        diff.get("count_diff", 0),
                        diff.get("traceback", "unknown"),
                    ]
                )

    @classmethod
    def is_micropython_import(cls, module_name: str) -> bool:
        """Return True if module_name is a known MicroPython hardware or built-in module."""
        return is_micropython_module(module_name)

    @classmethod
    def suggested_package_name(cls, module_name: str) -> str:
        """Return a likely PyPI package name for an import name."""
        if is_micropython_module(module_name):
            info = get_micropython_module_info(module_name)
            desc = f" ({info['description']})" if info and "description" in info else ""
            return f"micropython-stubs [MicroPython Built-in{desc}]"
        return cls._MODULE_PACKAGE_MAPPING.get(module_name, module_name)

    @staticmethod
    def initialize_diagnostics_state(service: DiagnosticsModel) -> tuple[list[tuple[str, float]], str | None]:
        """Initialize diagnostics service and return baseline history or an error message."""
        service.profile_memory_payload("start")
        result = service.profile_memory_payload("take_snapshot")
        if result.get("ok") and "total_allocated_kb" in result:
            return [(str(result.get("snapshot_name", "base_snapshot")), float(result["total_allocated_kb"]))], None
        return [], None

    @staticmethod
    def tracing_status(service: DiagnosticsModel) -> dict[str, object]:
        """Read current tracing status payload from diagnostics service."""
        return service.profile_memory_payload("status")

    @staticmethod
    def start_tracing(service: DiagnosticsModel, n_frames: int = 25) -> dict[str, object]:
        """Start tracing in diagnostics service."""
        return service.profile_memory_payload("start", n_frames=n_frames)

    @staticmethod
    def stop_tracing(service: DiagnosticsModel) -> dict[str, object]:
        """Stop tracing in diagnostics service."""
        return service.profile_memory_payload("stop")

    @staticmethod
    def take_snapshot(service: DiagnosticsModel, snapshot_name: str | None) -> dict[str, object]:
        """Take a snapshot through diagnostics service."""
        return service.profile_memory_payload("take_snapshot", snapshot_name=snapshot_name)

    @staticmethod
    def compare_snapshots(
        service: DiagnosticsModel,
        old_snapshot: str,
        new_snapshot: str,
    ) -> dict[str, object]:
        """Compare two snapshots through diagnostics service."""
        return service.profile_memory_payload("compare", snapshot_name=old_snapshot, other_snapshot_name=new_snapshot)

    @staticmethod
    def snapshot_result_text(result: dict[str, object]) -> str:
        """Format snapshot payload into user-facing text."""
        output = [
            f"Snapshot recorded: {result.get('snapshot_name')}",
            f"Total Allocated Memory: {result.get('total_allocated_kb', 0.0)} KB",
            "",
            "Top allocations:",
            f"{'Size (KB)':>10} | {'Count':>6} | Traceback Location",
            "-" * 60,
        ]
        for allocation in result.get("top_allocations", []):
            if not isinstance(allocation, dict):
                continue
            output.append(
                f"{float(allocation.get('size_kb', 0.0)):10.2f} | "
                f"{int(allocation.get('count', 0)):6d} | "
                f"{allocation.get('traceback', '')}"
            )
        return "\n".join(output)

    @staticmethod
    def comparison_result_text(result: dict[str, object], comparison_rows: list[dict[str, object]]) -> str:
        """Format compare payload into user-facing text."""
        output = [
            str(result.get("comparison", "Comparison results:")),
            "",
            f"{'Diff (KB)':>10} | {'Size (KB)':>10} | {'Count Diff':>10} | Location",
            "-" * 70,
        ]
        for diff in comparison_rows:
            output.append(
                f"{float(diff.get('size_diff_kb', 0.0)):10.2f} | "
                f"{float(diff.get('size_kb', 0.0)):10.2f} | "
                f"{int(diff.get('count_diff', 0)):10d} | "
                f"{diff.get('traceback', '')}"
            )
        return "\n".join(output)

    @staticmethod
    def missing_module_name(error_message: str) -> str | None:
        """Extract missing module import name from a traceback string."""
        match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", error_message)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def profiling_start_message(
        target_path: str | None,
        duration: int,
        interval: int,
        headless: bool,
    ) -> str:
        """Build startup message for profiling runs."""
        if target_path:
            return (
                f"Starting profiling for: {target_path}...\n"
                f"(Duration: {duration}s, Interval: {interval}s, Headless: {headless})\n"
                "(Please wait, profiling in a background process)"
            )
        return "Starting headless memory profiling...\n(Please wait, profiling IndexManager in a background process)"

    @staticmethod
    def profiling_result_text(result: dict[str, object]) -> str:
        """Format profiling result payload into user-facing text."""
        output = [
            "\n--- Profiling Completed ---",
            f"Cycles run: {result.get('cycles_run')}",
            f"Net memory growth: {result.get('size_growth_kb')} KB",
            f"Allocated Before: {result.get('total_allocated_before_kb')} KB",
            f"Allocated After: {result.get('total_allocated_after_kb')} KB",
            "",
            "Growth details by location (Top Diff > 0):",
            f"{'Growth (KB)':>12} | {'Total Size':>12} | {'Count Diff':>10} | Location",
            "-" * 80,
        ]
        for diff in result.get("top_differences", []):
            if not isinstance(diff, dict):
                continue
            traceback_value = diff.get("traceback")
            location = "unknown"
            if isinstance(traceback_value, list) and traceback_value:
                location = str(traceback_value[0])
            output.append(
                f"{float(diff.get('size_diff_kb', 0.0)):12.2f} | "
                f"{float(diff.get('size_kb', 0.0)):12.2f} | "
                f"{int(diff.get('count_diff', 0)):10d} | {location}"
            )
        return "\n".join(output)
