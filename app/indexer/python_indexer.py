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

"""Python symbol indexing using the standard library AST parser."""

from __future__ import annotations

import ast
from pathlib import Path


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return a lightweight signature string for a function-like node."""
    arg_names = [arg.arg for arg in node.args.args]
    return f"{node.name}({', '.join(arg_names)})"


def _record_skip(skipped_files: list[dict[str, str]] | None, path: Path, repo_root: Path, reason: str) -> None:
    """Append a normalized skipped-file record."""
    if skipped_files is None:
        return
    try:
        rel_path = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel_path = path.as_posix()
    skipped_files.append({"path": rel_path, "stage": "python_symbols", "reason": reason})


def _module_symbols(
    path: Path,
    repo_root: Path,
    skipped_files: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Extract class and function symbols from one Python file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except OSError as exc:
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason=f"read_error:{exc.__class__.__name__}")
        return []
    except SyntaxError:
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason="syntax_error")
        return []
    symbols: list[dict[str, object]] = []
    relative_path = path.relative_to(repo_root).as_posix()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(
                {
                    "name": node.name,
                    "qualified_name": node.name,
                    "kind": "class",
                    "line": node.lineno,
                    "path": relative_path,
                    "signature": node.name,
                    "doc_summary": (ast.get_docstring(node) or "").splitlines()[0:1][0] if ast.get_docstring(node) else "",
                }
            )
            for class_node in node.body:
                if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qn = f"{node.name}.{class_node.name}"
                    symbols.append(
                        {
                            "name": class_node.name,
                            "qualified_name": qn,
                            "kind": "method",
                            "line": class_node.lineno,
                            "path": relative_path,
                            "signature": _function_signature(class_node),
                            "doc_summary": (ast.get_docstring(class_node) or "").splitlines()[0:1][0]
                            if ast.get_docstring(class_node)
                            else "",
                        }
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                {
                    "name": node.name,
                    "qualified_name": node.name,
                    "kind": "function",
                    "line": node.lineno,
                    "path": relative_path,
                    "signature": _function_signature(node),
                    "doc_summary": (ast.get_docstring(node) or "").splitlines()[0:1][0] if ast.get_docstring(node) else "",
                }
            )
    return symbols


def index_python_symbols(repo_root: Path, skipped_files: list[dict[str, str]] | None = None) -> list[dict[str, object]]:
    """Index Python symbols for all source files beneath repo_root."""
    symbols: list[dict[str, object]] = []
    for path in sorted(repo_root.rglob("*.py")):
        if any(part.startswith(".") for part in path.parts):
            continue
        if "tests" in path.parts:
            continue
        if "build" in path.parts or "__pycache__" in path.parts:
            continue
        symbols.extend(_module_symbols(path=path, repo_root=repo_root, skipped_files=skipped_files))
    return symbols
