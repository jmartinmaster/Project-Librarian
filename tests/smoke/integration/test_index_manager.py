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

"""Smoke tests for index manager orchestration and persistence."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from app.indexer.index_manager import CORPUS_NAME, HISTORY_NAME, SNAPSHOT_NAME, IndexManager


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
