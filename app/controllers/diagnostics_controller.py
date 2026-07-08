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

"""Diagnostics workflow controller skeleton."""

from __future__ import annotations

import csv
import subprocess
import sys


class DiagnosticsController:
    """Controller seam for diagnostics orchestration behavior."""

    def install_package(self, package_name: str) -> tuple[bool, str]:
        """Install a package using the active Python environment."""
        try:
            cmd = [sys.executable, "-m", "pip", "install", package_name]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
