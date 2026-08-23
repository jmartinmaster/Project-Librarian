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
"""Symbol Call Graph, Reference Explorer, and Cross-File Dependency Analyzer."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


class CallGraphEngine:
    """Analyzes symbol references, callers, callees, and dependencies across Python & C/C++ codebases."""

    @staticmethod
    def analyze_symbol(
        repo_root: Path,
        symbol_name: str,
        symbols: list[dict[str, Any]] | None = None,
        file_corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Build a comprehensive call graph & reference map for the given symbol name.
        """
        symbol_clean = symbol_name.strip()
        if not symbol_clean:
            return {
                "symbol": "",
                "definition": None,
                "callers": [],
                "callees": [],
                "imports": [],
                "references_count": 0,
            }

        symbols = symbols or []
        file_corpus = file_corpus or []

        # 1. Locate symbol definition(s)
        matching_defs = [
            s for s in symbols
            if s.get("name") == symbol_clean or s.get("qualified_name") == symbol_clean
        ]
        primary_def = matching_defs[0] if matching_defs else None

        # 2. Extract callers / references across files
        callers = []
        # Match symbol invocation: symbol( or .symbol( or ->symbol( or ::symbol(
        call_regex = re.compile(rf"(?:\b|->|\.|::)({re.escape(symbol_clean)})\s*\(")
        ref_regex = re.compile(rf"\b({re.escape(symbol_clean)})\b")

        # Collect files to scan
        scan_paths: list[Path] = []
        if repo_root.exists():
            excluded = {".git", ".venv", "__pycache__", "build", "tests"}
            valid_exts = {".py", ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx", ".ino"}
            import os
            for root, dirs, files in os.walk(repo_root):
                dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in valid_exts:
                        scan_paths.append(Path(root) / f)

        for p in scan_paths:
            try:
                rel_path = p.relative_to(repo_root).as_posix()
                content = p.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()

                # Find which functions enclose which line numbers in this file
                file_symbols = [s for s in symbols if s.get("path") == rel_path]

                for line_idx, line_text in enumerate(lines):
                    line_num = line_idx + 1
                    
                    # Skip definition line itself
                    if primary_def and primary_def.get("path") == rel_path and primary_def.get("line") == line_num:
                        continue

                    # Check if line calls or references symbol
                    is_call = bool(call_regex.search(line_text))
                    is_ref = bool(ref_regex.search(line_text))

                    if is_call or is_ref:
                        # Find enclosing function / method
                        enclosing = "[global scope]"
                        for fs in file_symbols:
                            s_line = fs.get("line") or 0
                            e_line = fs.get("end_line") or (s_line + 50)
                            if s_line <= line_num <= e_line and fs.get("kind") in {"function", "method", "c_function", "cpp_method"}:
                                enclosing = fs.get("qualified_name") or fs.get("name") or enclosing
                                break

                        callers.append({
                            "file": rel_path,
                            "line": line_num,
                            "caller": enclosing,
                            "is_invocation": is_call,
                            "snippet": line_text.strip(),
                        })
            except Exception:
                pass

        # 3. Extract Callees & Outgoing Calls (what this symbol calls inside its body)
        callees = []
        imports = []
        if primary_def and primary_def.get("path"):
            def_path = repo_root / primary_def["path"]
            if def_path.exists() and def_path.is_file():
                try:
                    content = def_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    start_line = primary_def.get("line", 1) or 1
                    end_line = primary_def.get("end_line") or min(len(lines), start_line + 60)

                    # Extract body lines
                    body_lines = lines[start_line - 1 : end_line]
                    body_text = "\n".join(body_lines)

                    # Find all outgoing calls in body: word(
                    outgoing_matches = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", body_text)
                    seen_callees = set()
                    for callee_name in outgoing_matches:
                        if callee_name != symbol_clean and callee_name not in seen_callees and len(callee_name) > 1:
                            if callee_name not in {"if", "for", "while", "return", "print", "len", "range", "min", "max", "str", "int", "float", "isinstance", "getattr", "setattr", "assert"}:
                                seen_callees.add(callee_name)
                                # Lookup callee definition if indexed
                                callee_match = next((s for s in symbols if s.get("name") == callee_name), None)
                                callees.append({
                                    "name": callee_name,
                                    "target_file": callee_match.get("path") if callee_match else None,
                                    "target_line": callee_match.get("line") if callee_match else None,
                                    "kind": callee_match.get("kind") if callee_match else "function",
                                })

                    # Extract imports in this file
                    for l in lines[:40]:
                        l_str = l.strip()
                        if l_str.startswith("import ") or l_str.startswith("from ") or l_str.startswith("#include"):
                            imports.append(l_str)

                except Exception:
                    pass

        return {
            "symbol": symbol_clean,
            "definition": primary_def,
            "all_definitions": matching_defs,
            "callers": callers,
            "callees": callees,
            "imports": imports,
            "references_count": len(callers),
        }
