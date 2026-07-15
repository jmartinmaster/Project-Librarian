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

"""Anti-pattern workflow controller skeleton."""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

from app.controllers.path_controller import PathController
from app.indexer.index_manager import IndexManager
from app.models.anti_pattern_model import load_anti_pattern_config, save_anti_pattern_config
from app.models.editor_model import launch_editor
from app.models.format_checker import FormatChecker


class AntiPatternController:
    """Controller seam for anti-pattern browser orchestration."""

    def __init__(self, index_manager: IndexManager) -> None:
        self._index_manager = index_manager
        self._path_controller = PathController(index_manager=index_manager)

    def output_dir(self) -> Path:
        """Resolve configured output directory path."""
        output_candidate = Path(self._index_manager.config.output_dir)
        repo_root = Path(self._index_manager.config.project_root or Path.cwd()).resolve()
        return output_candidate if output_candidate.is_absolute() else repo_root / output_candidate

    def changed_paths(self) -> set[str]:
        """Return normalized changed file paths from git status."""
        repo_root = Path(self._index_manager.config.project_root or Path.cwd()).resolve()
        extra = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            **extra,
        )
        changed_paths: set[str] = set()
        for line in result.stdout.splitlines():
            if len(line) > 3:
                changed_paths.add(line[3:].strip().replace("\\", "/"))
        return changed_paths

    def load_presets(self) -> list[dict[str, object]]:
        """Load anti-pattern presets from persisted configuration."""
        config = load_anti_pattern_config(self.output_dir())
        presets = config.get("presets", [])
        return presets if isinstance(presets, list) else []

    def save_presets(self, presets: list[dict[str, object]]) -> None:
        """Persist anti-pattern presets."""
        save_anti_pattern_config(self.output_dir(), {"presets": presets})

    def run_scan(
        self,
        presets: list[dict[str, object]],
        scope: str,
        filter_text: str,
        run_format_checks: bool = False,
        enabled_format_rules: dict[str, bool] | None = None,
    ) -> list[dict[str, object]]:
        """Run anti-pattern regex scan and formatting checks, and return matched records."""
        compiled: list[tuple[dict[str, object], re.Pattern[str]]] = []
        for preset in presets:
            regex_text = str(preset.get("regex", ""))
            if not regex_text:
                continue
            try:
                compiled.append((preset, re.compile(regex_text)))
            except re.error:
                continue

        changed = self.changed_paths() if scope == "changed" else set()
        normalized_filter = filter_text.strip().lower()

        results: list[dict[str, object]] = []
        corpus = self._index_manager.state.file_corpus
        for rel_path, file_text in corpus.items():
            normalized_path = rel_path.replace("\\", "/")
            if normalized_filter and normalized_filter not in normalized_path.lower():
                continue
            if scope == "changed" and normalized_path not in changed:
                continue

            if presets:
                for line_idx, line in enumerate(file_text.splitlines(), start=1):
                    for preset, pattern in compiled:
                        for match in pattern.finditer(line):
                            results.append(
                                {
                                    "path": rel_path,
                                    "line": line_idx,
                                    "match": match.group(0),
                                    "preset_name": str(preset.get("name", "")),
                                    "description": str(preset.get("description", "")),
                                    "severity": str(preset.get("severity", "")),
                                    "content": line.strip(),
                                }
                            )

            if run_format_checks:
                file_results = FormatChecker.check_format(rel_path, file_text, enabled_format_rules)
                results.extend(file_results)

        results.sort(key=lambda x: (str(x.get("path", "")), int(x.get("line", 0))))
        return results

    def resolve_result_path(self, path_text: str) -> Path | None:
        """Resolve an anti-pattern result path against project root."""
        return self._path_controller.resolve_path(path_text)

    def reference_location(self, path_text: str, line_text: str) -> str:
        """Build path:line reference text for clipboard actions."""
        return self._path_controller.reference_location(path_text=path_text, line_text=line_text)

    def containing_folder_path(self, path_text: str) -> str:
        """Return absolute containing-folder path for clipboard actions."""
        return self._path_controller.containing_folder_path(path_text)

    def line_context(
        self,
        path: str,
        line_number: int | None,
        fallback_content: str,
        context: int = 4,
    ) -> str:
        """Build a line-context preview for a result using in-memory corpus."""
        source = self._index_manager.state.file_corpus.get(path, "")
        lines = source.splitlines()
        if not lines or line_number is None:
            return fallback_content

        start = max(1, line_number - context)
        end = min(len(lines), line_number + context)
        rendered: list[str] = []
        for ln in range(start, end + 1):
            marker = ">" if ln == line_number else " "
            rendered.append(f"{marker} {ln:4d} | {lines[ln - 1]}")
        return "\n".join(rendered)

    def open_external_editor(self, path_text: str, line_number: int | None) -> bool:
        """Open a result path in configured external editor."""
        resolved = self.resolve_result_path(path_text)
        if resolved is None or not resolved.exists():
            return False
        return launch_editor(resolved, line_number, self._index_manager.config)

    @staticmethod
    def export_results_to_csv(results: list[dict[str, object]], file_path: str) -> None:
        """Export anti-pattern scan results to a CSV file."""
        with open(file_path, "w", newline="", encoding="utf-8") as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow(["File", "Line", "Preset Name", "Severity", "Match", "Content"])
            for item in results:
                writer.writerow(
                    [
                        item.get("path", ""),
                        item.get("line", ""),
                        item.get("preset_name", ""),
                        item.get("severity", ""),
                        item.get("match", ""),
                        item.get("content", ""),
                    ]
                )
