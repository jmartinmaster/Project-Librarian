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
"""Controller-style index orchestration for Project Librarian."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import AppConfig
from app.indexer.c_indexer import index_c_symbols
from app.indexer.excel_indexer import index_excel_rows
from app.indexer.python_indexer import index_python_symbols


def _read_one_file_for_corpus(path: Path, repo_root: Path) -> tuple[str, str | None, list[dict[str, str]]]:
    local_skipped: list[dict[str, str]] = []
    try:
        rel_path = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel_path = path.as_posix()
    try:
        # Skip large files to prevent memory explosion or hanging
        if path.stat().st_size > MAX_CORPUS_FILE_BYTES:
            local_skipped.append({"path": rel_path, "stage": "file_corpus", "reason": "skip_large_file"})
            return rel_path, None, local_skipped
        text = path.read_text(encoding="utf-8", errors="replace")
        return rel_path, text, local_skipped
    except OSError as exc:
        local_skipped.append(
            {
                "path": rel_path,
                "stage": "file_corpus",
                "reason": f"read_error:{exc.__class__.__name__}",
            }
        )
        return rel_path, None, local_skipped
    except Exception as exc:
        # A single unexpected failure on one file must never abort the
        # whole corpus build (which would leave the index unrefreshed).
        local_skipped.append(
            {
                "path": rel_path,
                "stage": "file_corpus",
                "reason": f"unexpected_error:{exc.__class__.__name__}",
            }
        )
        return rel_path, None, local_skipped


SNAPSHOT_NAME = "librarian-snapshot.json"
CORPUS_NAME = "search-corpus.json"
HISTORY_NAME = "change-history.jsonl"


def _safe_write_text(path: Path, content: str, retries: int = 3, retry_delay: float = 0.1) -> None:
    """Write text content to a path with retries to handle transient file locks."""
    for attempt in range(retries):
        try:
            path.write_text(content, encoding="utf-8")
            return
        except (PermissionError, OSError):
            if attempt == retries - 1:
                raise
            time.sleep(retry_delay)


def _safe_append_line(path: Path, line: str, retries: int = 3, retry_delay: float = 0.1) -> None:
    """Append a line to a file with retries to handle transient file locks."""
    for attempt in range(retries):
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return
        except (PermissionError, OSError):
            if attempt == retries - 1:
                raise
            time.sleep(retry_delay)

# Files larger than this are skipped during corpus indexing (see
# `_read_one_file_for_corpus`) and are therefore excluded from RAM estimates.
MAX_CORPUS_FILE_BYTES = 5 * 1024 * 1024

# Multiplier applied to raw on-disk file bytes to approximate the actual
# in-memory footprint once files are loaded as Python strings and duplicated
# across the file corpus, symbol index, and generated snapshot/history
# artifacts kept in memory during a refresh.
RAM_OVERHEAD_MULTIPLIER = 3.0


def format_bytes(num_bytes: float) -> str:
    """Format a byte count as a short human-readable string (KB/MB/GB)."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def get_memory_usage() -> dict[str, object]:
    """Return current process RAM and system RAM statistics."""
    process_bytes = 0
    total_phys_bytes = 0
    avail_phys_bytes = 0
    mem_load_percent = 0

    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        psapi = getattr(ctypes.windll, "psapi", None)
        kernel32 = getattr(ctypes.windll, "kernel32", None)
        if kernel32:
            if psapi:
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
                psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
                if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                    process_bytes = int(counters.WorkingSetSize)

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                total_phys_bytes = int(mem.ullTotalPhys)
                avail_phys_bytes = int(mem.ullAvailPhys)
                mem_load_percent = int(mem.dwMemoryLoad)
    except Exception:
        pass

    if not process_bytes:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            import sys
            process_bytes = usage * 1024 if sys.platform != "darwin" else usage
        except Exception:
            pass

    return {
        "process_ram_bytes": process_bytes,
        "process_ram_text": format_bytes(process_bytes) if process_bytes else "--",
        "system_ram_total_bytes": total_phys_bytes,
        "system_ram_avail_bytes": avail_phys_bytes,
        "system_ram_load_percent": mem_load_percent,
        "system_ram_text": (
            f"{format_bytes(avail_phys_bytes)} free / {format_bytes(total_phys_bytes)} ({mem_load_percent}% used)"
            if total_phys_bytes
            else "--"
        ),
    }


@dataclass
class IndexState:
    """Current in-memory index payloads used by UI and search."""

    symbols: list[dict[str, object]]
    excel_rows: list[dict[str, object]]
    file_corpus: dict[str, str]
    skipped_files: list[dict[str, str]]


@dataclass
class ScanEstimate:
    """Result of scanning a folder to estimate load cost before indexing."""

    file_count: int
    skipped_large_count: int
    total_bytes: int
    estimated_ram_bytes: int
    cancelled: bool = False

    @property
    def total_size_text(self) -> str:
        """Human-readable on-disk size of files that will be loaded."""
        return format_bytes(self.total_bytes)

    @property
    def estimated_ram_text(self) -> str:
        """Human-readable estimated in-memory RAM footprint."""
        return format_bytes(self.estimated_ram_bytes)


class IndexManager:
    """Manage indexing runs and persist generated outputs."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = IndexState(symbols=[], excel_rows=[], file_corpus={}, skipped_files=[])
        self._refresh_lock = threading.RLock()
        self._refresh_run_lock = threading.Lock()
        self._worker_stop_event = threading.Event()
        self._exit_event = threading.Event()
        self._refresh_in_progress = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._manual_refresh_thread: threading.Thread | None = None
        self._worker_interval_seconds = max(0.0, float(self.config.refresh_interval_seconds))
        self._last_refresh_at: str | None = None
        self._refresh_count = 0
        self._last_refresh_error: str | None = None
        self._refresh_started_monotonic: float | None = None
        self._progress_stage: str | None = None
        self._progress_completed: int | None = None
        self._progress_total: int | None = None
        self._progress_percent: int | None = None
        self._file_signatures: dict[str, tuple[float, int]] = {}

    def _set_progress(
        self,
        stage: str | None,
        completed: int | None = None,
        total: int | None = None,
        percent: int | None = None,
    ) -> None:
        with self._refresh_lock:
            self._progress_stage = stage
            self._progress_completed = completed
            self._progress_total = total
            self._progress_percent = percent

    def is_refresh_worker_running(self) -> bool:
        """Return True when the background refresh worker is currently active."""
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def refresh_status(self) -> dict[str, object]:
        """Return current refresh worker/runtime metadata for UI display."""
        with self._refresh_lock:
            started_at = self._refresh_started_monotonic
            running_seconds = (time.monotonic() - started_at) if started_at is not None else None
            mem_info = get_memory_usage()
            return {
                "worker_running": self.is_refresh_worker_running(),
                "refresh_in_progress": self._refresh_in_progress.is_set(),
                "refresh_running_seconds": running_seconds,
                "progress_stage": self._progress_stage,
                "progress_percent": self._progress_percent,
                "progress_completed": self._progress_completed,
                "progress_total": self._progress_total,
                "process_ram_text": mem_info["process_ram_text"],
                "process_ram_bytes": mem_info["process_ram_bytes"],
                "system_ram_text": mem_info["system_ram_text"],
                "system_ram_load_percent": mem_info["system_ram_load_percent"],
                "interval_seconds": self._worker_interval_seconds,
                "last_refresh_at": self._last_refresh_at,
                "refresh_count": self._refresh_count,
                "skipped_count": len(self.state.skipped_files),
                "last_refresh_error": self._last_refresh_error,
            }

    def request_refresh_async(self) -> bool:
        """Schedule one background refresh when no refresh is currently active."""
        with self._refresh_lock:
            if self._refresh_in_progress.is_set():
                return False
            if self._manual_refresh_thread is not None and self._manual_refresh_thread.is_alive():
                return False

            self._manual_refresh_thread = threading.Thread(
                target=self._run_manual_refresh,
                name="librarian-refresh-request",
                daemon=True,
            )
            self._manual_refresh_thread.start()
            return True

    def start_refresh_worker(
        self,
        interval_seconds: float | None = None,
        force_restart: bool = False,
        run_immediately: bool = False,
    ) -> None:
        """Start (or restart) the background refresh worker with a safe interval."""
        configured_interval = (
            max(0.0, float(interval_seconds))
            if interval_seconds is not None
            else max(0.0, float(self.config.refresh_interval_seconds))
        )
        self._worker_interval_seconds = configured_interval

        if configured_interval <= 0:
            self.stop_refresh_worker()
            return

        if self.is_refresh_worker_running():
            if not force_restart:
                return
            self.stop_refresh_worker()

        self._worker_stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            kwargs={"run_immediately": run_immediately},
            name="librarian-refresh-worker",
            daemon=True,
        )
        self._worker_thread.start()

    def stop_refresh_worker(self, join_timeout: float = 2.0) -> None:
        """Stop the background refresh worker and wait briefly for shutdown."""
        self._worker_stop_event.set()
        worker = self._worker_thread
        self._worker_thread = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=max(0.0, float(join_timeout)))

    def estimate_scan(
        self,
        repo_root: str | Path | None = None,
        progress_callback: Callable[[ScanEstimate], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        progress_interval_seconds: float = 0.15,
    ) -> ScanEstimate:
        """Scan a folder and estimate the RAM required to load it as an index."""
        import os

        target_root = Path(repo_root).resolve() if repo_root is not None else self._repo_root()
        allowed = {ext.lower() for ext in self.config.file_extensions}
        excluded = set(self.config.excluded_dirs)

        file_count = 0
        skipped_large_count = 0
        total_bytes = 0
        cancelled = False
        last_progress_at = time.monotonic()

        def _emit_progress(force: bool = False) -> None:
            nonlocal last_progress_at
            if progress_callback is None:
                return
            now = time.monotonic()
            if not force and (now - last_progress_at) < progress_interval_seconds:
                return
            last_progress_at = now
            progress_callback(
                ScanEstimate(
                    file_count=file_count,
                    skipped_large_count=skipped_large_count,
                    total_bytes=total_bytes,
                    estimated_ram_bytes=int(total_bytes * RAM_OVERHEAD_MULTIPLIER),
                )
            )

        for root, dirs, files in os.walk(target_root):
            if cancel_check is not None and cancel_check():
                cancelled = True
                break
            dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
            for file in files:
                if cancel_check is not None and cancel_check():
                    cancelled = True
                    break
                ext = os.path.splitext(file)[1].lower()
                if ext not in allowed:
                    continue
                try:
                    size = (Path(root) / file).stat().st_size
                except OSError:
                    continue
                if size > MAX_CORPUS_FILE_BYTES:
                    skipped_large_count += 1
                    continue
                file_count += 1
                total_bytes += size
                _emit_progress()
            if cancelled:
                break

        _emit_progress(force=True)

        return ScanEstimate(
            file_count=file_count,
            skipped_large_count=skipped_large_count,
            total_bytes=total_bytes,
            estimated_ram_bytes=int(total_bytes * RAM_OVERHEAD_MULTIPLIER),
            cancelled=cancelled,
        )

    def shutdown(self) -> None:
        """Fully stop the manager and all running refreshes during app exit."""
        self._exit_event.set()
        self.stop_refresh_worker()
        manual_thread = self._manual_refresh_thread
        self._manual_refresh_thread = None
        if manual_thread is not None and manual_thread.is_alive():
            manual_thread.join(timeout=2.0)

    def _worker_loop(self, run_immediately: bool = False) -> None:
        """Run periodic refresh cycles until stopped."""
        if run_immediately and not self._worker_stop_event.is_set():
            try:
                self.refresh()
            except Exception as exc:
                self._record_refresh_error(exc)

        while not self._worker_stop_event.wait(timeout=self._worker_interval_seconds):
            try:
                self.refresh()
            except Exception as exc:
                self._record_refresh_error(exc)
                continue

    def _record_refresh_error(self, exc: Exception) -> None:
        """Store last refresh error text so the UI can surface failures."""
        with self._refresh_lock:
            self._last_refresh_error = f"{exc.__class__.__name__}: {exc}"

    def _run_manual_refresh(self) -> None:
        """Run a one-shot background refresh while preserving any raised error detail."""
        try:
            self.refresh()
        except Exception as exc:
            self._record_refresh_error(exc)

    def _repo_root(self) -> Path:
        return Path(self.config.project_root or Path.cwd()).resolve()

    def _output_dir(self) -> Path:
        repo_root = self._repo_root()
        output_candidate = Path(self.config.output_dir)
        output_path = output_candidate if output_candidate.is_absolute() else repo_root / output_candidate
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    def _build_file_corpus(
        self,
        repo_root: Path,
        skipped_files: list[dict[str, str]],
        cached_corpus: dict[str, str] | None = None,
        cached_signatures: dict[str, tuple[float, int]] | None = None,
    ) -> tuple[dict[str, str], dict[str, tuple[float, int]]]:
        allowed = {ext.lower() for ext in self.config.file_extensions}
        excluded = set(self.config.excluded_dirs)
        paths = []
        new_signatures: dict[str, tuple[float, int]] = {}

        import os
        for root, dirs, files in os.walk(repo_root):
            if self._exit_event.is_set():
                break
            dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in allowed:
                    paths.append(Path(root) / file)

        corpus: dict[str, str] = {}
        paths_to_read: list[Path] = []

        for p in paths:
            try:
                rel_path = p.relative_to(repo_root).as_posix()
            except ValueError:
                rel_path = p.as_posix()
            try:
                st = p.stat()
                sig = (st.st_mtime, st.st_size)
                new_signatures[rel_path] = sig
            except OSError:
                paths_to_read.append(p)
                continue

            if (
                cached_signatures is not None
                and cached_corpus is not None
                and rel_path in cached_signatures
                and cached_signatures[rel_path] == sig
                and rel_path in cached_corpus
            ):
                corpus[rel_path] = cached_corpus[rel_path]
            else:
                paths_to_read.append(p)

        if not paths_to_read:
            return corpus, new_signatures

        from concurrent.futures import ProcessPoolExecutor
        thread_count = getattr(self.config, 'indexing_thread_count', 4)
        total_paths = len(paths_to_read)
        completed_paths = 0
        self._set_progress("Building File Corpus", completed=0, total=total_paths, percent=60)
        with ProcessPoolExecutor(max_workers=max(1, thread_count)) as executor:
            futures = [executor.submit(_read_one_file_for_corpus, path, repo_root) for path in paths_to_read]
            for path, future in zip(paths_to_read, futures):
                if self._exit_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    res = future.result()
                except Exception as exc:
                    if skipped_files is not None:
                        try:
                            rel_path = path.relative_to(repo_root).as_posix()
                        except ValueError:
                            rel_path = path.as_posix()
                        skipped_files.append(
                            {"path": rel_path, "stage": "file_corpus", "reason": f"worker_error:{exc.__class__.__name__}"}
                        )
                    completed_paths += 1
                    pct = 60 + int(35 * completed_paths / max(1, total_paths))
                    self._set_progress("Building File Corpus", completed=completed_paths, total=total_paths, percent=pct)
                    continue
                completed_paths += 1
                pct = 60 + int(35 * completed_paths / max(1, total_paths))
                self._set_progress("Building File Corpus", completed=completed_paths, total=total_paths, percent=pct)
                if res is None:
                    continue
                rel_path, text, local_skipped = res
                if text is not None:
                    corpus[rel_path] = text
                if local_skipped and skipped_files is not None:
                    skipped_files.extend(local_skipped)

        return corpus, new_signatures

    def refresh(self, force_full: bool = False) -> IndexState:
        """Rebuild all configured indexes and persist snapshot artifacts."""
        with self._refresh_run_lock:
            self._refresh_in_progress.set()
            with self._refresh_lock:
                self._refresh_started_monotonic = time.monotonic()
            try:
                repo_root = self._repo_root()
                output_dir = self._output_dir()
                skipped_files: list[dict[str, str]] = []

                use_incremental = (
                    getattr(self.config, "incremental_indexing", True)
                    and not force_full
                    and bool(self.state.file_corpus)
                )
                cached_symbols = self.state.symbols if use_incremental else None
                cached_sigs = self._file_signatures if use_incremental else None

                symbols: list[dict[str, object]] = []
                thread_count = getattr(self.config, 'indexing_thread_count', 4)
                excluded_dirs = self.config.excluded_dirs
                cst_max_size = getattr(self.config, 'cst_max_file_size_kb', 200)
                cst_excluded = getattr(self.config, 'cst_excluded_paths', [])

                if self.config.index_python:
                    self._set_progress("Scanning Python symbols", percent=10)
                    symbols.extend(index_python_symbols(
                        repo_root,
                        skipped_files=skipped_files,
                        use_cst=self.config.use_cst,
                        thread_count=thread_count,
                        excluded_dirs=excluded_dirs,
                        cst_max_file_size_kb=cst_max_size,
                        cst_excluded_paths=cst_excluded,
                        cached_symbols=cached_symbols,
                        cached_signatures=cached_sigs,
                    ))
                if self.config.index_c:
                    self._set_progress("Scanning C/H symbols", percent=35)
                    symbols.extend(index_c_symbols(
                        repo_root,
                        skipped_files=skipped_files,
                        thread_count=thread_count,
                        excluded_dirs=excluded_dirs,
                        cached_symbols=cached_symbols,
                        cached_signatures=cached_sigs,
                    ))

                excel_rows: list[dict[str, object]] = []
                if self.config.excel_folder:
                    self._set_progress("Indexing Excel files", percent=50)
                    excel_rows = index_excel_rows(
                        folder_path=(repo_root / self.config.excel_folder).resolve(),
                        keyword_columns=self.config.excel_keyword_columns,
                        skipped_files=skipped_files,
                    )

                self._set_progress("Building File Corpus", percent=60)
                cached_corpus = self.state.file_corpus if use_incremental else None
                file_corpus, new_signatures = self._build_file_corpus(
                    repo_root=repo_root,
                    skipped_files=skipped_files,
                    cached_corpus=cached_corpus,
                    cached_signatures=cached_sigs,
                )
                self._file_signatures = new_signatures

                next_state = IndexState(
                    symbols=symbols,
                    excel_rows=excel_rows,
                    file_corpus=file_corpus,
                    skipped_files=skipped_files,
                )
                generated_at = datetime.now(timezone.utc).isoformat()
                summary = {
                    "files": len(file_corpus),
                    "symbols": len(symbols),
                    "excel_rows": len(excel_rows),
                    "skipped_files": len(skipped_files),
                }
                snapshot = {
                    "generated_at": generated_at,
                    "repo_root": str(repo_root),
                    "summary": summary,
                    "symbols": symbols,
                    "skipped_files": skipped_files,
                }

                self._set_progress("Saving Index Snapshots", percent=95)
                _safe_write_text(output_dir / SNAPSHOT_NAME, json.dumps(snapshot, indent=2))
                _safe_write_text(output_dir / CORPUS_NAME, json.dumps(file_corpus))
                history_line = json.dumps({"generated_at": generated_at, "summary": summary}, ensure_ascii=True)
                _safe_append_line(output_dir / HISTORY_NAME, history_line)

                with self._refresh_lock:
                    self.state = next_state
                    self._last_refresh_at = generated_at
                    self._refresh_count += 1
                    self._last_refresh_error = None
                    return self.state
            except Exception as exc:
                self._record_refresh_error(exc)
                raise
            finally:
                self._refresh_in_progress.clear()
                self._set_progress(None, completed=None, total=None, percent=None)
                with self._refresh_lock:
                    self._refresh_started_monotonic = None
