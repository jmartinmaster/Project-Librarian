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
import threading
import time
from datetime import datetime, timezone

from PyQt6.QtWidgets import QApplication, QTabWidget


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

    def test_navigation_leaks_payload(self, cycles: int = 5) -> dict:
        """Perform loop cycles of UI tab-switching, collecting memory statistics to detect leaks."""
        import tracemalloc

        app = QApplication.instance()
        if not app:
            return {"error": "QApplication instance not found"}

        tab_widget = None
        for widget in app.topLevelWidgets():
            tab_widgets = widget.findChildren(QTabWidget)
            if tab_widgets:
                tab_widget = tab_widgets[0]
                break

        if not tab_widget:
            return {"error": "tabWidget not found in top level widgets"}

        if not tracemalloc.is_tracing():
            tracemalloc.start(25)

        error_container = []

        # 1. Warm up navigation elements
        try:
            num_tabs = tab_widget.count()
            original_index = tab_widget.currentIndex()
            for tab_idx in range(num_tabs):
                tab_widget.setCurrentIndex(tab_idx)
                app.processEvents()
            tab_widget.setCurrentIndex(original_index)
            app.processEvents()
        except Exception as e:
            error_container.append(str(e))

        if error_container:
            return {"error": f"Warmup failed: {error_container[0]}"}

        # Clean up memory to baseline
        for _ in range(3):
            gc.collect()

        baseline_snapshot = tracemalloc.take_snapshot()

        # 2. Run cycles of navigation
        try:
            num_tabs = tab_widget.count()
            original_index = tab_widget.currentIndex()
            for cycle_idx in range(cycles):
                for tab_idx in range(num_tabs):
                    tab_widget.setCurrentIndex(tab_idx)
                    app.processEvents()
                    time.sleep(0.05)
            tab_widget.setCurrentIndex(original_index)
            app.processEvents()
        except Exception as e:
            error_container.append(str(e))

        if error_container:
            return {"error": error_container[0]}

        for _ in range(3):
            gc.collect()

        current_snapshot = tracemalloc.take_snapshot()
        stats = current_snapshot.compare_to(baseline_snapshot, "lineno")

        top_differences = []
        for s in stats[:20]:
            if s.size_diff > 0:
                top_differences.append({
                    "size_diff_kb": round(s.size_diff / 1024, 2),
                    "size_kb": round(s.size / 1024, 2),
                    "count_diff": s.count_diff,
                    "count": s.count,
                    "traceback": [str(frame) for frame in s.traceback],
                })

        total_allocated_after_kb = round(sum(s.size for s in current_snapshot.statistics("lineno")) / 1024, 2)
        total_allocated_before_kb = round(sum(s.size for s in baseline_snapshot.statistics("lineno")) / 1024, 2)
        size_growth_kb = round(total_allocated_after_kb - total_allocated_before_kb, 2)

        return {
            "cycles_run": cycles,
            "total_allocated_before_kb": total_allocated_before_kb,
            "total_allocated_after_kb": total_allocated_after_kb,
            "size_growth_kb": size_growth_kb,
            "top_differences": top_differences,
        }
