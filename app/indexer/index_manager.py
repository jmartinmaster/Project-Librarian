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

"""Controller-style index orchestration for Project Librarian."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import AppConfig
from app.indexer.c_indexer import index_c_symbols
from app.indexer.excel_indexer import index_excel_rows
from app.indexer.python_indexer import index_python_symbols


def _read_one_file_for_corpus(path: Path, repo_root: Path) -> tuple[str, str | None, list[dict[str, str]]]:
    local_skipped: list[dict[str, str]] = []
    rel_path = path.relative_to(repo_root).as_posix()
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


SNAPSHOT_NAME = "librarian-snapshot.json"
CORPUS_NAME = "search-corpus.json"
HISTORY_NAME = "change-history.jsonl"

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

    def is_refresh_worker_running(self) -> bool:
        """Return True when the background refresh worker is currently active."""
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def refresh_status(self) -> dict[str, object]:
        """Return current refresh worker/runtime metadata for UI display."""
        with self._refresh_lock:
            return {
                "worker_running": self.is_refresh_worker_running(),
                "refresh_in_progress": self._refresh_in_progress.is_set(),
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

    def estimate_scan(self, repo_root: str | Path | None = None) -> ScanEstimate:
        """Scan a folder and estimate the RAM required to load it as an index.

        Walks the given folder (or the configured project root when omitted)
        counting indexable files that match the configured extensions and
        exclusions, without reading their contents. This lets the UI warn the
        user about large workspaces before a full refresh is triggered.
        """
        import os

        target_root = Path(repo_root).resolve() if repo_root is not None else self._repo_root()
        allowed = {ext.lower() for ext in self.config.file_extensions}
        excluded = set(self.config.excluded_dirs)

        file_count = 0
        skipped_large_count = 0
        total_bytes = 0

        for root, dirs, files in os.walk(target_root):
            dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
            for file in files:
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

        return ScanEstimate(
            file_count=file_count,
            skipped_large_count=skipped_large_count,
            total_bytes=total_bytes,
            estimated_ram_bytes=int(total_bytes * RAM_OVERHEAD_MULTIPLIER),
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
                # Keep worker alive despite transient refresh errors.
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

    def _build_file_corpus(self, repo_root: Path, skipped_files: list[dict[str, str]]) -> dict[str, str]:
        allowed = {ext.lower() for ext in self.config.file_extensions}
        excluded = set(self.config.excluded_dirs)
        paths = []

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
        # Using ProcessPoolExecutor to offload CPU-bound parsing/reading to separate processes.
        # This bypasses the Python GIL and ensures the PyQt6 UI thread remains fully responsive.
        from concurrent.futures import ProcessPoolExecutor
        thread_count = getattr(self.config, 'indexing_thread_count', 4)
        with ProcessPoolExecutor(max_workers=max(1, thread_count)) as executor:
            # We map across the module-level function because sub-processes require picklable top-level functions.
            results = executor.map(_read_one_file_for_corpus, paths, [repo_root] * len(paths))
            for res in results:
                # Cancel pending futures instantly if the application is shutting down.
                if self._exit_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                if res is None:
                    continue
                rel_path, text, local_skipped = res
                if text is not None:
                    corpus[rel_path] = text
                if local_skipped and skipped_files is not None:
                    skipped_files.extend(local_skipped)

        return corpus

    def refresh(self) -> IndexState:
        """Rebuild all configured indexes and persist snapshot artifacts."""
        with self._refresh_run_lock:
            self._refresh_in_progress.set()
            try:
                repo_root = self._repo_root()
                output_dir = self._output_dir()
                skipped_files: list[dict[str, str]] = []

                symbols: list[dict[str, object]] = []
                thread_count = getattr(self.config, 'indexing_thread_count', 4)
                if self.config.index_python:
                    symbols.extend(index_python_symbols(
                        repo_root,
                        skipped_files=skipped_files,
                        use_cst=self.config.use_cst,
                        thread_count=thread_count,
                    ))
                if self.config.index_c:
                    symbols.extend(index_c_symbols(
                        repo_root,
                        skipped_files=skipped_files,
                        thread_count=thread_count,
                    ))

                excel_rows: list[dict[str, object]] = []
                if self.config.excel_folder:
                    excel_rows = index_excel_rows(
                        folder_path=(repo_root / self.config.excel_folder).resolve(),
                        keyword_columns=self.config.excel_keyword_columns,
                        skipped_files=skipped_files,
                    )

                file_corpus = self._build_file_corpus(repo_root=repo_root, skipped_files=skipped_files)
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

                (output_dir / SNAPSHOT_NAME).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
                (output_dir / CORPUS_NAME).write_text(json.dumps(file_corpus), encoding="utf-8")
                history_line = json.dumps({"generated_at": generated_at, "summary": summary}, ensure_ascii=True)
                with (output_dir / HISTORY_NAME).open("a", encoding="utf-8") as handle:
                    handle.write(history_line + "\n")

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
