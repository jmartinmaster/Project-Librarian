#!/usr/bin/env python3
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
"""Master script to run pytest tests in parallel using separate child processes.

This script discovers test files matching `test_*.py` under the specified paths
(defaulting to the `tests` directory) and runs each file in a separate child
process. This avoids issues with multiple QApplications in PyQt tests and
allows full utilization of multiple CPU cores.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path

# Terminal color escape sequences
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def enable_ansi_colors() -> None:
    """Enable virtual terminal processing on Windows to support ANSI colors."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # GetStdHandle(-11) returns STD_OUTPUT_HANDLE
            stdout_handle = kernel32.GetStdHandle(-11)
            # Get current mode
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode))
            # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
        except Exception:
            # Fall back silently if ANSI enabling fails
            pass


def main() -> int:
    enable_ansi_colors()
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Run pytest tests in parallel using child processes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Number of parallel worker processes. Defaults to CPU count.",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Optional paths to test files/folders, and/or options to forward to pytest (e.g. -v, -k pattern).",
    )

    args = parser.parse_known_args()
    parsed_args, extra_args = args
    workers = parsed_args.workers or multiprocessing.cpu_count()

    # Split positional paths from other flags in extra/pytest arguments
    paths: list[str] = []
    other_args: list[str] = []
    
    # We combine pytest_args and extra_args (from parse_known_args)
    combined_pytest_args = parsed_args.pytest_args + extra_args

    for arg in combined_pytest_args:
        # Check if the argument is a path that exists
        if Path(arg).exists():
            paths.append(arg)
        else:
            other_args.append(arg)

    # Discover test files
    test_files: list[Path] = []
    if paths:
        for p in paths:
            path_obj = Path(p)
            if path_obj.is_file():
                test_files.append(path_obj)
            elif path_obj.is_dir():
                test_files.extend(path_obj.rglob("test_*.py"))
    else:
        test_files = list(Path("tests").rglob("test_*.py"))

    # Ensure uniqueness and sort to run consistently
    test_files = sorted(list(set(test_files)))

    if not test_files:
        print(f"{YELLOW}No test files found matching the criteria.{RESET}")
        return 0

    print(f"{BOLD}Starting parallel test execution across {len(test_files)} file(s) with {workers} worker(s)...{RESET}\n")

    # Worker queue / processes management
    active_processes: dict[subprocess.Popen, tuple[Path, float]] = {}
    pending_files = list(test_files)
    completed_results: list[tuple[Path, bool, float, str, str]] = []
    failed_files: list[Path] = []

    start_time_all = time.time()

    try:
        while pending_files or active_processes:
            # Spawn new processes up to max workers limit
            while pending_files and len(active_processes) < workers:
                file_path = pending_files.pop(0)
                # Build command: python -m pytest <file_path> <other_args>
                cmd = [sys.executable, "-m", "pytest", str(file_path)] + other_args
                p = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                active_processes[p] = (file_path, time.time())

            # Check status of active processes
            finished: list[subprocess.Popen] = []
            for p, (file_path, start_time) in active_processes.items():
                returncode = p.poll()
                if returncode is not None:
                    # Process completed, capture output
                    stdout, stderr = p.communicate()
                    duration = time.time() - start_time
                    success = (returncode == 0)
                    completed_results.append((file_path, success, duration, stdout, stderr))

                    # Print progress line
                    idx = len(completed_results)
                    total = len(test_files)
                    if success:
                        status_str = f"{GREEN}PASSED{RESET}"
                    else:
                        status_str = f"{RED}FAILED{RESET}"
                        failed_files.append(file_path)

                    print(f"[{idx}/{total}] {file_path} {status_str} ({duration:.2f}s)")
                    finished.append(p)

            # Remove finished processes
            for p in finished:
                del active_processes[p]

            # Avoid tight looping
            time.sleep(0.02)

    except KeyboardInterrupt:
        print(f"\n{RED}Received KeyboardInterrupt. Terminating all active test processes...{RESET}")
        for p in active_processes:
            try:
                p.terminate()
            except Exception:
                pass
        return 130

    total_duration = time.time() - start_time_all
    print(f"\n{BOLD}============================== SUMMARY =============================={RESET}")
    print(f"Total test files: {len(test_files)}")
    print(f"Passed:           {GREEN}{len(test_files) - len(failed_files)}{RESET}")
    print(f"Failed:           {RED if failed_files else GREEN}{len(failed_files)}{RESET}")
    print(f"Total time:       {total_duration:.2f}s")
    print(f"{BOLD}====================================================================={RESET}\n")

    # If there are failures, print out their captured stdout & stderr at the end
    if failed_files:
        print(f"{RED}{BOLD}Failed Test Details:{RESET}")
        for file_path, success, duration, stdout, stderr in completed_results:
            if not success:
                print(f"\n{RED}---------------------------------------------------------------------")
                print(f"FAIL: {file_path} (Duration: {duration:.2f}s)")
                print(f"---------------------------------------------------------------------{RESET}")
                if stdout.strip():
                    print(f"{BOLD}Stdout:{RESET}\n{stdout}")
                if stderr.strip():
                    print(f"{BOLD}Stderr:{RESET}\n{stderr}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
