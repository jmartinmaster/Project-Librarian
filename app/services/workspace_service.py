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

"""Workspace-oriented helpers ported from the legacy monolith into a modular service."""

from __future__ import annotations

import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from app.indexer.index_manager import IndexManager

AREA_ORDER = ("app", "controllers", "models", "views", "docs", "scripts", "root")


class WorkspaceServiceError(RuntimeError):
    """Raised when workspace helper operations fail."""


class WorkspaceService:
    """Provide git snapshot summaries and docs/changelog draft generation."""

    def __init__(self, index_manager: IndexManager) -> None:
        self.index_manager = index_manager

    @property
    def repo_root(self) -> Path:
        """Return configured repository root."""
        return Path(self.index_manager.config.project_root or Path.cwd()).resolve()

    @property
    def output_dir(self) -> Path:
        """Return configured output directory under the repository root when relative."""
        configured = Path(self.index_manager.config.output_dir)
        return configured if configured.is_absolute() else (self.repo_root / configured).resolve()

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a git command against the current repository root."""
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo_root),
            check=False,
            capture_output=True,
            text=True,
        )

    def _run_git_text(self, args: list[str], fallback: str = "") -> str:
        """Run git command and return trimmed stdout or fallback when command fails."""
        completed = self._run_git(args)
        if completed.returncode != 0:
            return fallback
        return (completed.stdout or "").strip() or fallback

    def _file_area(self, path_text: str) -> str:
        """Infer a coarse codebase area from repository-relative path."""
        normalized = path_text.replace("\\", "/").strip("/")
        if not normalized:
            return "root"
        head = normalized.split("/", maxsplit=1)[0]
        if head in {"app", "controllers", "models", "views", "docs", "scripts"}:
            return head
        return "root"

    @staticmethod
    def _counts_from_items(items: list[dict[str, object]], key_name: str) -> dict[str, int]:
        """Build stable counts for one record key."""
        counts: dict[str, int] = {}
        for item in items:
            key = str(item.get(key_name) or "")
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda pair: pair[0]))

    def _run_git_status(self) -> list[dict[str, str]]:
        """Collect git porcelain changed-file records."""
        completed = self._run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"])
        if completed.returncode != 0:
            return []
        entries = (completed.stdout or "").split("\0")
        changed_files: list[dict[str, str]] = []
        index = 0
        while index < len(entries):
            entry = entries[index]
            index += 1
            if not entry:
                continue
            raw_status = entry[:2]
            status = raw_status.strip() or "??"
            path_text = entry[3:].replace("\\", "/")
            record = {
                "status": status,
                "xy": raw_status,
                "path": path_text,
                "area": self._file_area(path_text),
            }
            if "R" in status or "C" in status:
                source_path = entries[index] if index < len(entries) else ""
                if source_path:
                    record["source_path"] = source_path.replace("\\", "/")
                    index += 1
            changed_files.append(record)
        return changed_files

    def _collect_recent_commits(self, limit: int = 5) -> list[dict[str, str]]:
        """Collect a small recent commit summary list."""
        completed = self._run_git(
            [
                "log",
                f"--max-count={max(1, int(limit))}",
                "--date=short",
                "--pretty=format:%H%x1f%h%x1f%ad%x1f%an%x1f%s",
            ]
        )
        if completed.returncode != 0 or not (completed.stdout or "").strip():
            return []
        commits: list[dict[str, str]] = []
        for line in (completed.stdout or "").splitlines():
            parts = line.split("\x1f")
            if len(parts) != 5:
                continue
            commits.append(
                {
                    "commit": parts[0],
                    "short_commit": parts[1],
                    "date": parts[2],
                    "author": parts[3],
                    "subject": parts[4],
                }
            )
        return commits

    def collect_git_snapshot(self, commit_limit: int = 5) -> dict[str, object]:
        """Collect current branch/change/commit metadata."""
        changed_files = self._run_git_status()
        branch = self._run_git_text(["rev-parse", "--abbrev-ref", "HEAD"], fallback="unknown")
        return {
            "branch": branch,
            "changed_files": changed_files,
            "changed_count": len(changed_files),
            "status_counts": self._counts_from_items(changed_files, "status"),
            "area_counts": self._counts_from_items(changed_files, "area"),
            "recent_commits": self._collect_recent_commits(limit=commit_limit),
        }

    def format_git_summary(self, limit: int = 20) -> str:
        """Render a plain-text git status summary."""
        snapshot = self.collect_git_snapshot(commit_limit=5)
        changed_files = list(snapshot.get("changed_files", []))
        lines = [
            f"Branch: {snapshot.get('branch', 'unknown')}",
            f"Changed Files: {len(changed_files)}",
        ]
        status_counts = snapshot.get("status_counts", {})
        if isinstance(status_counts, dict) and status_counts:
            lines.append("Statuses: " + ", ".join(f"{key}={value}" for key, value in status_counts.items()))
        area_counts = snapshot.get("area_counts", {})
        if isinstance(area_counts, dict) and area_counts:
            lines.append("Areas: " + ", ".join(f"{key}={value}" for key, value in area_counts.items()))

        if changed_files:
            lines.append("")
            lines.append("Changed Paths:")
            for record in changed_files[: max(1, int(limit))]:
                source_path = str(record.get("source_path") or "")
                if source_path:
                    lines.append(
                        f"- {record.get('status', '??')} [{record.get('area', 'root')}]: "
                        f"{source_path} -> {record.get('path', '')}"
                    )
                else:
                    lines.append(f"- {record.get('status', '??')} [{record.get('area', 'root')}]: {record.get('path', '')}")
        else:
            lines.append("")
            lines.append("No tracked git changes.")

        commits = snapshot.get("recent_commits", [])
        if isinstance(commits, list) and commits:
            lines.append("")
            lines.append("Recent Commits:")
            for commit in commits[:3]:
                lines.append(
                    f"- {commit.get('short_commit', '')} {commit.get('date', '')} "
                    f"{commit.get('subject', '')} ({commit.get('author', '')})"
                )

        return "\n".join(lines)

    @staticmethod
    def _utc_now_text() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _today_text() -> str:
        return date.today().isoformat()

    def _selected_records(self, changed_only: bool) -> list[dict[str, str]]:
        """Build selected file records from changed files or full indexed corpus."""
        if changed_only:
            changed_files = self.collect_git_snapshot(commit_limit=5).get("changed_files", [])
            records: list[dict[str, str]] = []
            if isinstance(changed_files, list):
                for entry in changed_files:
                    path_text = str(entry.get("path") or "").replace("\\", "/")
                    if not path_text:
                        continue
                    records.append({"path": path_text, "area": self._file_area(path_text), "status": str(entry.get("status") or "")})
            return records

        return [{"path": path_text, "area": self._file_area(path_text)} for path_text in sorted(self.index_manager.state.file_corpus.keys())]

    def _touched_symbols_for_records(self, records: list[dict[str, str]]) -> dict[str, list[str]]:
        """Map selected file paths to touched symbol labels."""
        selected_paths = {str(record.get("path") or "") for record in records}
        touched: dict[str, list[str]] = {}
        for symbol in self.index_manager.state.symbols:
            path_text = str(symbol.get("path") or "").replace("\\", "/")
            if path_text not in selected_paths:
                continue
            symbol_label = str(symbol.get("qualified_name") or symbol.get("name") or "").strip()
            if not symbol_label:
                continue
            touched.setdefault(path_text, [])
            if symbol_label not in touched[path_text]:
                touched[path_text].append(symbol_label)
        return touched

    def _records_grouped_by_area(self, records: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = {}
        for record in records:
            area = str(record.get("area") or "root")
            grouped.setdefault(area, []).append(record)
        return grouped

    def generate_docs_draft(self, title: str | None = None, changed_only: bool = True) -> str:
        """Generate markdown documentation update draft."""
        records = self._selected_records(changed_only=changed_only)
        grouped = self._records_grouped_by_area(records)
        touched_symbols = self._touched_symbols_for_records(records)
        git_snapshot = self.collect_git_snapshot(commit_limit=5)

        lines = [
            f"# {title or 'Project Documentation Update Draft'}",
            "",
            f"- Generated: {self._utc_now_text()}",
            f"- Branch: {git_snapshot.get('branch', 'unknown')}",
            f"- Scope: {'changed files only' if changed_only else 'full indexed workspace'}",
            "",
            "## Draft Notes",
            "",
        ]
        if grouped:
            for area in AREA_ORDER:
                area_records = grouped.get(area, [])
                if not area_records:
                    continue
                sample_paths = ", ".join(str(record.get("path") or "") for record in area_records[:4])
                suffix = "..." if len(area_records) > 4 else ""
                lines.append(f"- {area}: updated {len(area_records)} file(s) ({sample_paths}{suffix})")
        else:
            lines.append("- No files selected for this draft.")

        lines.extend(["", "## Touched Symbols", ""])
        if touched_symbols:
            for path_text in sorted(touched_symbols.keys()):
                labels = touched_symbols[path_text][:5]
                lines.append(f"- {path_text}: {', '.join(labels)}")
        else:
            lines.append("- No symbol-level changes inferred in current scope.")

        recent_commits = git_snapshot.get("recent_commits", [])
        lines.extend(["", "## Recent Commit Context", ""])
        if isinstance(recent_commits, list) and recent_commits:
            for commit in recent_commits[:4]:
                lines.append(f"- {commit.get('subject', '')}")
        else:
            lines.append("- No recent commit subjects were available.")
        lines.append("")
        return "\n".join(lines)

    def generate_changelog_draft(
        self,
        version_text: str | None = None,
        release_date: str | None = None,
        changed_only: bool = True,
    ) -> str:
        """Generate a markdown changelog section draft."""
        records = self._selected_records(changed_only=changed_only)
        grouped = self._records_grouped_by_area(records)
        touched_symbols = self._touched_symbols_for_records(records)
        git_snapshot = self.collect_git_snapshot(commit_limit=4)

        version_label = version_text or "Unreleased"
        date_label = release_date or self._today_text()
        lines = [
            f"## [{version_label}] - {date_label}",
            "",
            "### Changed",
            "",
        ]
        if grouped:
            for area in AREA_ORDER:
                area_records = grouped.get(area, [])
                if not area_records:
                    continue
                symbols = []
                for record in area_records:
                    record_path = str(record.get("path") or "")
                    symbols.extend(touched_symbols.get(record_path, [])[:1])
                symbols_text = f" (symbols: {', '.join(symbols[:4])})" if symbols else ""
                lines.append(f"- {area}: {len(area_records)} file(s) updated{symbols_text}")
        else:
            lines.append("- No tracked changes were available for this draft.")

        lines.extend(["", "### Notes", ""])
        lines.append(f"- Branch at draft time: {git_snapshot.get('branch', 'unknown')}")
        lines.append(f"- Snapshot generated at: {self._utc_now_text()}")
        lines.append(f"- Files considered: {len(records)}")
        recent_commits = git_snapshot.get("recent_commits", [])
        if isinstance(recent_commits, list) and recent_commits:
            subjects = [str(item.get("subject") or "").strip() for item in recent_commits if str(item.get("subject") or "").strip()]
            if subjects:
                lines.append(f"- Recent commit context: {' | '.join(subjects[:4])}")
        lines.append("")
        return "\n".join(lines)

    def save_draft(self, content: str, prefix: str) -> Path:
        """Persist generated markdown draft under build/drafts and return its file path."""
        drafts_dir = self.output_dir / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in {"-", "_"}).strip("_-") or "draft"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = drafts_dir / f"{safe_prefix}-{timestamp}.md"
        target.write_text(content, encoding="utf-8")
        return target
