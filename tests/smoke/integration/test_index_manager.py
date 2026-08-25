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
"""Smoke tests for index manager orchestration and persistence."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from app.indexer.index_manager import (
    CORPUS_NAME,
    HISTORY_NAME,
    MAX_CORPUS_FILE_BYTES,
    SNAPSHOT_NAME,
    IndexManager,
    format_bytes,
    get_memory_usage,
)


def test_refresh_builds_in_memory_and_persisted_outputs(app_config, sample_repo: Path):
    manager = IndexManager(app_config)
    state = manager.refresh()

    assert state.file_corpus
    assert state.symbols

    output_dir = sample_repo / "build"
    assert (output_dir / SNAPSHOT_NAME).exists()
    assert (output_dir / CORPUS_NAME).exists()
    assert (output_dir / HISTORY_NAME).exists()


def test_refresh_worker_runs_at_interval(monkeypatch, app_config):
    manager = IndexManager(app_config)
    counter = {"calls": 0}

    def fake_refresh():
        counter["calls"] += 1
        return manager.state

    monkeypatch.setattr(manager, "refresh", fake_refresh)

    manager.start_refresh_worker(interval_seconds=0.05)
    time.sleep(0.18)
    manager.stop_refresh_worker(join_timeout=1.0)

    assert counter["calls"] >= 2


def test_refresh_worker_stops_safely(monkeypatch, app_config):
    manager = IndexManager(app_config)
    counter = {"calls": 0}

    def fake_refresh():
        counter["calls"] += 1
        return manager.state

    monkeypatch.setattr(manager, "refresh", fake_refresh)

    manager.start_refresh_worker(interval_seconds=0.05)
    time.sleep(0.12)
    manager.stop_refresh_worker(join_timeout=1.0)
    calls_after_stop = counter["calls"]

    time.sleep(0.12)
    assert counter["calls"] == calls_after_stop
    assert not manager.is_refresh_worker_running()


def test_refresh_worker_can_run_immediately(monkeypatch, app_config):
    manager = IndexManager(app_config)
    counter = {"calls": 0}

    def fake_refresh():
        counter["calls"] += 1
        return manager.state

    monkeypatch.setattr(manager, "refresh", fake_refresh)

    manager.start_refresh_worker(interval_seconds=1.0, run_immediately=True)
    time.sleep(0.05)
    manager.stop_refresh_worker(join_timeout=1.0)

    assert counter["calls"] >= 1


def test_refresh_worker_immediate_run_does_not_block_main_thread(monkeypatch, app_config):
    manager = IndexManager(app_config)
    main_thread_id = threading.get_ident()
    refresh_started = threading.Event()
    release_refresh = threading.Event()
    observed_thread_ids: list[int] = []

    def fake_refresh():
        observed_thread_ids.append(threading.get_ident())
        refresh_started.set()
        release_refresh.wait(timeout=1.0)
        return manager.state

    monkeypatch.setattr(manager, "refresh", fake_refresh)

    start = time.perf_counter()
    manager.start_refresh_worker(interval_seconds=1.0, run_immediately=True)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.1
    assert refresh_started.wait(timeout=0.2)
    assert observed_thread_ids
    assert observed_thread_ids[0] != main_thread_id

    release_refresh.set()
    manager.stop_refresh_worker(join_timeout=1.0)


def test_refresh_status_does_not_wait_for_background_refresh(monkeypatch, app_config):
    manager = IndexManager(app_config)
    release_refresh = threading.Event()

    def fake_repo_root():
        release_refresh.wait(timeout=1.0)
        return Path(app_config.project_root)

    monkeypatch.setattr(manager, "_repo_root", fake_repo_root)

    manager.start_refresh_worker(interval_seconds=1.0, run_immediately=True)
    time.sleep(0.05)

    start = time.perf_counter()
    status = manager.refresh_status()
    elapsed = time.perf_counter() - start

    assert elapsed < 0.1
    assert status["worker_running"] is True

    release_refresh.set()
    manager.stop_refresh_worker(join_timeout=1.0)


def test_request_refresh_async_returns_without_blocking(monkeypatch, app_config):
    manager = IndexManager(app_config)
    refresh_started = threading.Event()
    release_refresh = threading.Event()

    def fake_refresh():
        refresh_started.set()
        release_refresh.wait(timeout=1.0)
        return manager.state

    monkeypatch.setattr(manager, "refresh", fake_refresh)

    start = time.perf_counter()
    started = manager.request_refresh_async()
    elapsed = time.perf_counter() - start

    assert started is True
    assert elapsed < 0.1
    assert refresh_started.wait(timeout=0.2)

    release_refresh.set()
    time.sleep(0.05)


def test_refresh_status_tracks_last_refresh_and_count(app_config):
    manager = IndexManager(app_config)
    before = manager.refresh_status()
    assert before["refresh_count"] == 0
    assert before["last_refresh_at"] is None
    assert before["skipped_count"] == 0

    manager.refresh()
    after = manager.refresh_status()
    assert after["refresh_count"] >= 1
    assert isinstance(after["last_refresh_at"], str)
    assert isinstance(after["skipped_count"], int)


def test_refresh_status_reports_elapsed_running_time_while_in_progress(monkeypatch, app_config):
    """The status bar shows a ticking elapsed-time counter while a refresh is
    active, so a long-running (or stuck) scan is visibly distinguishable from
    a frozen UI instead of just showing a static "in progress" flag."""
    manager = IndexManager(app_config)
    release_refresh = threading.Event()
    refresh_entered = threading.Event()

    def fake_repo_root():
        refresh_entered.set()
        release_refresh.wait(timeout=1.0)
        return Path(app_config.project_root)

    monkeypatch.setattr(manager, "_repo_root", fake_repo_root)

    idle_status = manager.refresh_status()
    assert idle_status["refresh_running_seconds"] is None

    manager.start_refresh_worker(interval_seconds=1.0, run_immediately=True)
    assert refresh_entered.wait(timeout=1.0)

    running_status = manager.refresh_status()
    assert running_status["refresh_in_progress"] is True
    assert running_status["refresh_running_seconds"] is not None
    assert running_status["refresh_running_seconds"] >= 0

    release_refresh.set()
    manager.stop_refresh_worker(join_timeout=5.0)

    final_status = manager.refresh_status()
    assert final_status["refresh_running_seconds"] is None


def test_refresh_handles_non_utf8_and_malformed_python_files(app_config, sample_repo: Path):
    invalid_text = sample_repo / "latin1_text.txt"
    invalid_text.write_bytes(b"ol\xfc index me")

    malformed_py = sample_repo / "broken_encoding.py"
    malformed_py.write_bytes(b"def bad():\n    return \xfc\n")

    manager = IndexManager(app_config)
    state = manager.refresh()

    assert "latin1_text.txt" in state.file_corpus
    assert "ol" in state.file_corpus["latin1_text.txt"]
    assert any(item.get("path") == "broken_encoding.py" for item in state.skipped_files)
    assert manager.refresh_status()["skipped_count"] >= 1


def test_request_refresh_async_records_last_refresh_error(monkeypatch, app_config):
    manager = IndexManager(app_config)

    def failing_refresh():
        raise RuntimeError("boom")

    monkeypatch.setattr(manager, "refresh", failing_refresh)
    started = manager.request_refresh_async()
    assert started is True

    time.sleep(0.05)
    status = manager.refresh_status()
    assert status["last_refresh_error"] == "RuntimeError: boom"


def test_refresh_worker_records_last_refresh_error(monkeypatch, app_config):
    manager = IndexManager(app_config)

    def failing_refresh():
        raise ValueError("worker-failure")

    monkeypatch.setattr(manager, "refresh", failing_refresh)
    manager.start_refresh_worker(interval_seconds=1.0, run_immediately=True)
    time.sleep(0.05)
    status = manager.refresh_status()
    manager.stop_refresh_worker(join_timeout=1.0)

    assert status["last_refresh_error"] == "ValueError: worker-failure"


def test_estimate_scan_counts_indexable_files_and_ram(app_config, sample_repo: Path):
    manager = IndexManager(app_config)

    estimate = manager.estimate_scan(sample_repo)

    assert estimate.file_count == 2
    assert estimate.skipped_large_count == 0
    assert estimate.total_bytes > 0
    assert estimate.estimated_ram_bytes > estimate.total_bytes
    assert "B" in estimate.total_size_text
    assert "B" in estimate.estimated_ram_text


def test_estimate_scan_defaults_to_configured_project_root(app_config, sample_repo: Path):
    manager = IndexManager(app_config)

    estimate = manager.estimate_scan()

    assert estimate.file_count == 2


def test_estimate_scan_skips_oversized_files(app_config, sample_repo: Path):
    huge_file = sample_repo / "huge.txt"
    huge_file.write_bytes(b"0" * (MAX_CORPUS_FILE_BYTES + 1))

    manager = IndexManager(app_config)
    estimate = manager.estimate_scan(sample_repo)

    assert estimate.skipped_large_count == 1
    assert estimate.file_count == 2


def test_estimate_scan_respects_extension_and_exclusion_filters(app_config, sample_repo: Path):
    ignored_dir = sample_repo / "build"
    ignored_dir.mkdir()
    (ignored_dir / "generated.py").write_text("x = 1\n", encoding="utf-8")
    (sample_repo / "notes.rst").write_text("ignored extension\n", encoding="utf-8")

    manager = IndexManager(app_config)
    estimate = manager.estimate_scan(sample_repo)

    # Only the original sample.py/sample.c count; excluded dir and unmatched
    # extension are not included.
    assert estimate.file_count == 2


def test_estimate_scan_reports_progress_and_final_totals_match(app_config, sample_repo: Path):
    manager = IndexManager(app_config)
    updates = []

    estimate = manager.estimate_scan(
        sample_repo,
        progress_callback=updates.append,
        progress_interval_seconds=0.0,
    )

    assert estimate.cancelled is False
    assert len(updates) >= 1
    assert updates[-1].file_count == estimate.file_count
    assert updates[-1].total_bytes == estimate.total_bytes
    # Progress should never overshoot the final totals.
    assert all(update.file_count <= estimate.file_count for update in updates)


def test_estimate_scan_stops_early_when_cancelled(app_config, sample_repo: Path):
    manager = IndexManager(app_config)

    estimate = manager.estimate_scan(sample_repo, cancel_check=lambda: True)

    assert estimate.cancelled is True
    assert estimate.file_count == 0


def test_format_bytes_produces_readable_units():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_get_memory_usage_returns_dict_with_formatted_strings():
    mem = get_memory_usage()
    assert isinstance(mem, dict)
    assert "process_ram_bytes" in mem
    assert "process_ram_text" in mem
    assert "system_ram_total_bytes" in mem
    assert "system_ram_avail_bytes" in mem
    assert "system_ram_text" in mem
    assert isinstance(mem["process_ram_bytes"], int)


def test_refresh_status_reports_progress_and_memory_fields(app_config, sample_repo: Path):
    manager = IndexManager(app_config)
    status = manager.refresh_status()

    assert "progress_stage" in status
    assert "progress_percent" in status
    assert "process_ram_text" in status
    assert "system_ram_text" in status
    assert status["progress_stage"] is None
    assert status["progress_percent"] is None

    manager.refresh()
    post_status = manager.refresh_status()
    assert post_status["refresh_count"] == 1
    assert post_status["process_ram_text"] != ""


def test_incremental_refresh_preserves_and_updates_cache(app_config, sample_repo: Path):
    app_config.incremental_indexing = True
    manager = IndexManager(app_config)

    # Initial refresh
    state1 = manager.refresh()
    assert len(state1.file_corpus) > 0
    assert len(manager._file_signatures) == len(state1.file_corpus)
    initial_signatures = dict(manager._file_signatures)

    # Second refresh without file changes (instant incremental)
    state2 = manager.refresh()
    assert state2.file_corpus == state1.file_corpus
    assert manager._file_signatures == initial_signatures

    # Modify one file
    mod_file = sample_repo / "pkg" / "module_a.py"
    if mod_file.exists():
        mod_file.write_text("def added_function(): pass\n", encoding="utf-8")
        state3 = manager.refresh()
        assert "def added_function(): pass\n" in state3.file_corpus.get("pkg/module_a.py", "")


def test_cst_guard_and_skip_paths(app_config, sample_repo: Path):
    app_config.use_cst = True
    app_config.cst_max_file_size_kb = 1  # Low threshold: 1KB
    app_config.cst_excluded_paths = ["skip_folder/"]
    manager = IndexManager(app_config)

    # Create a 2KB python file (exceeds threshold)
    large_file = sample_repo / "large_file.py"
    large_file.write_text("# filler\n" * 150 + "def big_func(): pass\n", encoding="utf-8")

    # Create a file inside skip_folder
    skip_dir = sample_repo / "skip_folder"
    skip_dir.mkdir(parents=True, exist_ok=True)
    skip_file = skip_dir / "skipped.py"
    skip_file.write_text("def skip_func(): pass\n", encoding="utf-8")

    state = manager.refresh()
    symbol_names = [s.get("name") for s in state.symbols]
    assert "big_func" in symbol_names
    assert "skip_func" in symbol_names



