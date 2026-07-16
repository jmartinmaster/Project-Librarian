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
"""Memory profiling and leak testing service."""

from __future__ import annotations

from datetime import datetime, timezone


class DiagnosticsModel:
    """Service to handle memory allocation tracing and snapshot comparison."""

    def __init__(self) -> None:
        self._tracemalloc_snapshots: dict[str, object] = {}

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

        if normalized_action == "stop":
            if not is_tracing:
                return {"ok": True, "message": "Memory profiling is not active."}
            tracemalloc.stop()
            self._tracemalloc_snapshots.clear()
            return {"ok": True, "message": "Memory profiling stopped, all saved snapshots cleared."}

        if normalized_action == "status":
            snapshots_list = list(self._tracemalloc_snapshots.keys())
            return {
                "active": is_tracing,
                "saved_snapshots_count": len(snapshots_list),
                "saved_snapshots": snapshots_list,
                "message": "Tracing is active." if is_tracing else "Tracing is inactive.",
            }

        if normalized_action == "take_snapshot":
            if not is_tracing:
                tracemalloc.start(n_frames)
            snapshot = tracemalloc.take_snapshot()
            name = snapshot_name or f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            self._tracemalloc_snapshots[name] = snapshot

            stats = snapshot.statistics(key_type)
            return {
                "ok": True,
                "snapshot_name": name,
                "total_allocated_kb": round(sum(stat.size for stat in stats) / 1024, 2),
                "top_allocations": [
                    {"size_kb": round(stat.size / 1024, 2), "count": stat.count, "traceback": str(stat.traceback)}
                    for stat in stats[:limit]
                ],
            }

        if normalized_action == "get_stats":
            if not self._tracemalloc_snapshots:
                return {"ok": False, "error": "No saved snapshots found. Take a snapshot first."}
            name = snapshot_name or list(self._tracemalloc_snapshots.keys())[-1]
            snapshot = self._tracemalloc_snapshots.get(name)
            if not snapshot:
                return {"ok": False, "error": f"Snapshot '{name}' not found."}
            stats = snapshot.statistics(key_type)
            return {
                "snapshot_name": name,
                "total_allocated_kb": round(sum(stat.size for stat in stats) / 1024, 2),
                "top_allocations": [
                    {"size_kb": round(stat.size / 1024, 2), "count": stat.count, "traceback": str(stat.traceback)}
                    for stat in stats[:limit]
                ],
            }

        if normalized_action == "compare":
            if not self._tracemalloc_snapshots:
                return {"ok": False, "error": "No snapshots saved yet."}
            if not snapshot_name or not other_snapshot_name:
                return {"ok": False, "error": "Both snapshot_name and other_snapshot_name are required."}
            older_snapshot = self._tracemalloc_snapshots.get(snapshot_name)
            newer_snapshot = self._tracemalloc_snapshots.get(other_snapshot_name)
            if not older_snapshot:
                return {"ok": False, "error": f"Snapshot '{snapshot_name}' not found."}
            if not newer_snapshot:
                return {"ok": False, "error": f"Snapshot '{other_snapshot_name}' not found."}
            stats = newer_snapshot.compare_to(older_snapshot, key_type)
            return {
                "comparison": f"Comparing '{other_snapshot_name}' (new) to '{snapshot_name}' (old)",
                "top_differences": [
                    {
                        "size_diff_kb": round(stat.size_diff / 1024, 2),
                        "size_kb": round(stat.size / 1024, 2),
                        "count_diff": stat.count_diff,
                        "count": stat.count,
                        "traceback": str(stat.traceback),
                    }
                    for stat in stats[:limit]
                ],
            }

        if normalized_action == "clear":
            self._tracemalloc_snapshots.clear()
            return {"ok": True, "message": "All saved snapshots cleared."}

        return {"ok": False, "error": f"Unknown action '{action}'"}
