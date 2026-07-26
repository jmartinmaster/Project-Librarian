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
"""Workspace-oriented helpers ported from the legacy monolith into a modular service."""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from app.indexer.index_manager import IndexManager

AREA_ORDER = ("app", "controllers", "models", "views", "docs", "scripts", "root")


class WorkspaceModelError(RuntimeError):
    """Raised when workspace helper operations fail."""


class WorkspaceModel:
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
            encoding="utf-8",
            errors="replace",
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

    def _collect_git_diff_summary(self, max_chars: int = 4000) -> str:
        """Collect a brief git diff summary for changes in scope."""
        completed = self._run_git(["diff", "HEAD"])
        if completed.returncode != 0 or not (completed.stdout or "").strip():
            completed = self._run_git(["diff"])
        text = (completed.stdout or "").strip()
        if len(text) > max_chars:
            return text[:max_chars] + "\n... [diff output truncated]"
        return text

    def _try_ai_docs_draft(
        self,
        title: str | None,
        changed_only: bool,
        records: list[dict[str, str]],
        grouped: dict[str, list[dict[str, str]]],
        touched_symbols: dict[str, list[str]],
        git_snapshot: dict[str, object],
        diff_summary: str,
    ) -> str | None:
        """Attempt to generate a documentation draft using Ollama/AI service if reachable."""
        try:
            from app.models.ai_generator import AIGenerationService
            generator = AIGenerationService()

            prompt_context = {
                "title": title or "Project Documentation Update Draft",
                "scope": "changed files only" if changed_only else "full indexed workspace",
                "branch": git_snapshot.get("branch", "unknown"),
                "files_count": len(records),
                "areas": list(grouped.keys()),
                "file_records": records,
                "touched_symbols": touched_symbols,
                "recent_commits": git_snapshot.get("recent_commits", []),
                "git_diff_snippet": diff_summary,
            }

            prompt = (
                f"Generate a comprehensive, professional Markdown project documentation update draft based on the following codebase details:\n\n"
                f"{json.dumps(prompt_context, indent=2)}\n\n"
                f"Structure the document into:\n"
                f"# Title\n"
                f"- Metadata (Date, Branch, Scope, Files Tracked)\n"
                f"## Executive Summary\n"
                f"## Component Updates\n"
                f"## Touched Symbols & API Reference\n"
                f"## Verification & Commit Context\n\n"
                f"Provide clear, readable descriptions for developers and users. Output ONLY the raw Markdown document without code blocks surrounding the full response."
            )

            result = generator.generate_text(prompt, timeout=15.0)
            if result and len(result.strip()) > 50:
                return result.strip()
        except Exception:
            pass
        return None

    def _build_structured_docs_draft(
        self,
        title: str | None,
        changed_only: bool,
        records: list[dict[str, str]],
        grouped: dict[str, list[dict[str, str]]],
        touched_symbols: dict[str, list[str]],
        git_snapshot: dict[str, object],
    ) -> str:
        doc_title = title or "Project Documentation Update Draft"
        utc_now = self._utc_now_text()
        branch = git_snapshot.get("branch", "unknown")
        scope_str = "changed files only" if changed_only else "full indexed workspace"
        recent_commits = git_snapshot.get("recent_commits", [])

        lines = [
            f"# {doc_title}",
            "",
            f"- Generated: {utc_now}",
            f"- Branch: {branch}",
            f"- Scope: {scope_str}",
            f"- Files Tracked: {len(records)}",
            "",
            "## Executive Summary",
            "",
        ]

        if records:
            areas_list = ", ".join(grouped.keys())
            commit_summary = ""
            if isinstance(recent_commits, list) and recent_commits:
                subjects = [str(c.get("subject") or "") for c in recent_commits[:3] if str(c.get("subject") or "")]
                if subjects:
                    commit_summary = f" Recent updates focus on: {'; '.join(subjects)}."
            lines.append(
                f"This documentation update reflects changes across {len(records)} file(s) in {len(grouped)} area(s) "
                f"({areas_list}).{commit_summary}"
            )
        else:
            lines.append("No files were selected for this documentation update scope.")

        lines.extend(["", "## Component Updates", ""])

        if grouped:
            for area in AREA_ORDER:
                area_records = grouped.get(area, [])
                if not area_records:
                    continue
                lines.append(f"### Area: `{area}`")
                lines.append("")
                for record in area_records:
                    p = str(record.get("path") or "")
                    st = str(record.get("status") or "").strip()
                    status_desc = {
                        "M": "Modified",
                        "A": "Added",
                        "??": "Untracked / New",
                        "D": "Deleted",
                        "R": "Renamed",
                    }.get(st, st or "Indexed")

                    symbols = touched_symbols.get(p, [])
                    sym_str = f" (`{', '.join(symbols[:5])}`)" if symbols else ""
                    lines.append(f"- **`{p}`** [{status_desc}]{sym_str}")
                lines.append("")
        else:
            lines.append("No component updates registered in this scope.\n")

        lines.extend(["## Touched Symbols & API Reference", ""])
        if touched_symbols:
            for path_text in sorted(touched_symbols.keys()):
                symbols = touched_symbols[path_text]
                lines.append(f"### `{path_text}`")
                for sym in symbols:
                    lines.append(f"- `{sym}`: Symbol identified in workspace index.")
                lines.append("")
        else:
            lines.append("- No symbol-level changes inferred in current scope.\n")

        lines.extend(["## Verification & Commit Context", ""])
        if isinstance(recent_commits, list) and recent_commits:
            for commit in recent_commits[:5]:
                short_c = str(commit.get("short_commit") or "")
                subj = str(commit.get("subject") or "")
                author = str(commit.get("author") or "")
                date_c = str(commit.get("date") or "")
                lines.append(f"- `{short_c}` {subj} ({author}, {date_c})")
        else:
            lines.append("- No recent commit subjects were available.")

        lines.append("")
        return "\n".join(lines)

    def generate_docs_draft(self, title: str | None = None, changed_only: bool = True) -> str:
        """Generate markdown documentation update draft."""
        records = self._selected_records(changed_only=changed_only)
        grouped = self._records_grouped_by_area(records)
        touched_symbols = self._touched_symbols_for_records(records)
        git_snapshot = self.collect_git_snapshot(commit_limit=5)
        diff_summary = self._collect_git_diff_summary() if changed_only else ""

        ai_draft = self._try_ai_docs_draft(
            title=title,
            changed_only=changed_only,
            records=records,
            grouped=grouped,
            touched_symbols=touched_symbols,
            git_snapshot=git_snapshot,
            diff_summary=diff_summary,
        )
        if ai_draft:
            return ai_draft

        return self._build_structured_docs_draft(
            title=title,
            changed_only=changed_only,
            records=records,
            grouped=grouped,
            touched_symbols=touched_symbols,
            git_snapshot=git_snapshot,
        )

    def _try_ai_changelog_draft(
        self,
        version_text: str | None,
        release_date: str | None,
        changed_only: bool,
        records: list[dict[str, str]],
        grouped: dict[str, list[dict[str, str]]],
        touched_symbols: dict[str, list[str]],
        git_snapshot: dict[str, object],
        diff_summary: str,
    ) -> str | None:
        """Attempt to generate a changelog draft using Ollama/AI service if reachable."""
        try:
            from app.models.ai_generator import AIGenerationService
            generator = AIGenerationService()
            version_label = version_text or "Unreleased"
            date_label = release_date or self._today_text()

            prompt_context = {
                "version": version_label,
                "date": date_label,
                "branch": git_snapshot.get("branch", "unknown"),
                "files_count": len(records),
                "file_records": records,
                "touched_symbols": touched_symbols,
                "recent_commits": git_snapshot.get("recent_commits", []),
                "git_diff_snippet": diff_summary,
            }

            prompt = (
                f"Generate a professional, Keep a Changelog compliant Markdown changelog section draft based on these codebase details:\n\n"
                f"{json.dumps(prompt_context, indent=2)}\n\n"
                f"Structure the document with:\n"
                f"## [{version_label}] - {date_label}\n"
                f"Executive Summary quote\n"
                f"### Added\n"
                f"### Changed\n"
                f"### Fixed\n"
                f"### Removed\n"
                f"### Technical & Release Notes\n"
                f"Ensure bullet points describe functional impact based on commit subjects and changed files. Output ONLY the raw Markdown document without code fences wrapping the full output."
            )

            result = generator.generate_text(prompt, timeout=15.0)
            if result and len(result.strip()) > 50:
                return result.strip()
        except Exception:
            pass
        return None

    def _build_structured_changelog_draft(
        self,
        version_text: str | None,
        release_date: str | None,
        changed_only: bool,
        records: list[dict[str, str]],
        grouped: dict[str, list[dict[str, str]]],
        touched_symbols: dict[str, list[str]],
        git_snapshot: dict[str, object],
    ) -> str:
        version_label = version_text or "Unreleased"
        date_label = release_date or self._today_text()
        recent_commits = git_snapshot.get("recent_commits", [])

        added_records = []
        changed_records = []
        fixed_records = []
        removed_records = []

        for record in records:
            st = str(record.get("status") or "").strip()
            if st in ("A", "??"):
                added_records.append(record)
            elif st == "D":
                removed_records.append(record)
            else:
                changed_records.append(record)

        fix_commits = []
        if isinstance(recent_commits, list):
            for c in recent_commits:
                subj = str(c.get("subject") or "")
                if any(kw in subj.lower() for kw in ("fix:", "fix", "bug", "resolve", "patch")):
                    fix_commits.append(c)

        lines = [
            f"## [{version_label}] - {date_label}",
            "",
        ]

        if recent_commits and isinstance(recent_commits, list):
            highlights = [str(c.get("subject") or "").strip() for c in recent_commits[:3] if str(c.get("subject") or "").strip()]
            if highlights:
                lines.append(f"> **Release Summary**: {'; '.join(highlights)}.")
                lines.append("")

        lines.append("### Added")
        if added_records:
            for r in added_records:
                p = str(r.get("path") or "")
                syms = touched_symbols.get(p, [])
                sym_text = f" (symbols: {', '.join(syms[:3])})" if syms else ""
                lines.append(f"- Added new module `{p}`{sym_text}.")
        else:
            lines.append("- No new files added in this release.")
        lines.append("")

        lines.append("### Changed")
        if changed_records:
            for r in changed_records:
                p = str(r.get("path") or "")
                syms = touched_symbols.get(p, [])
                sym_text = f" (symbols: {', '.join(syms[:4])})" if syms else ""
                lines.append(f"- Updated `{p}`{sym_text}.")
        else:
            lines.append("- No tracked files modified in this release.")
        lines.append("")

        lines.append("### Fixed")
        if fix_commits:
            for c in fix_commits:
                lines.append(f"- {c.get('subject', '')} (`{c.get('short_commit', '')}`)")
        else:
            lines.append("- General bug fixes and stability updates.")
        lines.append("")

        if removed_records:
            lines.append("### Removed")
            for r in removed_records:
                lines.append(f"- Removed `{str(r.get('path') or '')}`.")
            lines.append("")

        lines.append("### Notes")
        lines.append(f"- Branch at draft time: {git_snapshot.get('branch', 'unknown')}")
        lines.append(f"- Snapshot generated at: {self._utc_now_text()}")
        lines.append(f"- Files considered: {len(records)}")
        if isinstance(recent_commits, list) and recent_commits:
            subjects = [str(item.get("subject") or "").strip() for item in recent_commits if str(item.get("subject") or "").strip()]
            if subjects:
                lines.append(f"- Recent commit context: {' | '.join(subjects[:4])}")
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
        diff_summary = self._collect_git_diff_summary() if changed_only else ""

        ai_draft = self._try_ai_changelog_draft(
            version_text=version_text,
            release_date=release_date,
            changed_only=changed_only,
            records=records,
            grouped=grouped,
            touched_symbols=touched_symbols,
            git_snapshot=git_snapshot,
            diff_summary=diff_summary,
        )
        if ai_draft:
            return ai_draft

        return self._build_structured_changelog_draft(
            version_text=version_text,
            release_date=release_date,
            changed_only=changed_only,
            records=records,
            grouped=grouped,
            touched_symbols=touched_symbols,
            git_snapshot=git_snapshot,
        )

    def save_draft(self, content: str, prefix: str) -> Path:
        """Persist generated markdown draft under build/drafts and return its file path."""
        drafts_dir = self.output_dir / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in {"-", "_"}).strip("_-") or "draft"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = drafts_dir / f"{safe_prefix}-{timestamp}.md"
        target.write_text(content, encoding="utf-8")
        return target
