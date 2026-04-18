"""Smoke tests for index manager orchestration and persistence."""

from __future__ import annotations

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
