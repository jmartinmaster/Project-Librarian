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

SNAPSHOT_NAME = "librarian-snapshot.json"
CORPUS_NAME = "search-corpus.json"
HISTORY_NAME = "change-history.jsonl"


@dataclass
class IndexState:
    """Current in-memory index payloads used by UI and search."""

    symbols: list[dict[str, object]]
    excel_rows: list[dict[str, object]]
    file_corpus: dict[str, str]
    skipped_files: list[dict[str, str]]


class IndexManager:
    """Manage indexing runs and persist generated outputs."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = IndexState(symbols=[], excel_rows=[], file_corpus={}, skipped_files=[])
        self._refresh_lock = threading.RLock()
        self._refresh_run_lock = threading.Lock()
        self._worker_stop_event = threading.Event()
        self._refresh_in_progress = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._manual_refresh_thread: threading.Thread | None = None
        self._worker_interval_seconds = max(0.0, float(self.config.refresh_interval_seconds))
        self._last_refresh_at: str | None = None
        self._refresh_count = 0

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
            }

    def request_refresh_async(self) -> bool:
        """Schedule one background refresh when no refresh is currently active."""
        with self._refresh_lock:
            if self._refresh_in_progress.is_set():
                return False
            if self._manual_refresh_thread is not None and self._manual_refresh_thread.is_alive():
                return False

            self._manual_refresh_thread = threading.Thread(
                target=self.refresh,
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

    def _worker_loop(self, run_immediately: bool = False) -> None:
        """Run periodic refresh cycles until stopped."""
        if run_immediately and not self._worker_stop_event.is_set():
            try:
                self.refresh()
            except Exception:
                # Keep worker alive despite transient refresh errors.
                pass

        while not self._worker_stop_event.wait(timeout=self._worker_interval_seconds):
            try:
                self.refresh()
            except Exception:
                # Keep worker alive despite transient refresh errors.
                continue

    def _repo_root(self) -> Path:
        return Path(self.config.project_root or Path.cwd()).resolve()

    def _output_dir(self) -> Path:
        repo_root = self._repo_root()
        output_candidate = Path(self.config.output_dir)
        output_path = output_candidate if output_candidate.is_absolute() else repo_root / output_candidate
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    def _build_file_corpus(self, repo_root: Path, skipped_files: list[dict[str, str]]) -> dict[str, str]:
        corpus: dict[str, str] = {}
        allowed = {ext.lower() for ext in self.config.file_extensions}
        excluded = set(self.config.excluded_dirs)

        for path in sorted(repo_root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in excluded for part in path.parts):
                continue
            if path.suffix.lower() not in allowed:
                continue
            try:
                # Preserve indexing progress even when repositories contain mixed encodings.
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                skipped_files.append(
                    {
                        "path": path.relative_to(repo_root).as_posix(),
                        "stage": "file_corpus",
                        "reason": f"read_error:{exc.__class__.__name__}",
                    }
                )
                continue
            corpus[path.relative_to(repo_root).as_posix()] = text
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
                if self.config.index_python:
                    symbols.extend(index_python_symbols(repo_root, skipped_files=skipped_files))
                if self.config.index_c:
                    symbols.extend(index_c_symbols(repo_root, skipped_files=skipped_files))

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
                    return self.state
            finally:
                self._refresh_in_progress.clear()
