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
"""C symbol indexing via pycparser."""

from __future__ import annotations

from pathlib import Path

from pycparser import c_ast, c_parser


class _SymbolVisitor(c_ast.NodeVisitor):
    """Collect top-level C symbols from a parsed AST."""

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self.symbols: list[dict[str, object]] = []

    def visit_FuncDef(self, node: c_ast.FuncDef) -> None:  # noqa: N802
        decl = node.decl
        line = decl.coord.line if decl.coord else None
        self.symbols.append(
            {
                "name": decl.name,
                "qualified_name": decl.name,
                "kind": "c_function",
                "line": line,
                "path": self._file_path,
                "signature": decl.name,
                "doc_summary": "",
            }
        )

    def visit_Struct(self, node: c_ast.Struct) -> None:  # noqa: N802
        if not node.name:
            return
        line = node.coord.line if node.coord else None
        self.symbols.append(
            {
                "name": node.name,
                "qualified_name": f"struct {node.name}",
                "kind": "c_struct",
                "line": line,
                "path": self._file_path,
                "signature": f"struct {node.name}",
                "doc_summary": "",
            }
        )

    def visit_Enum(self, node: c_ast.Enum) -> None:  # noqa: N802
        if not node.name:
            return
        line = node.coord.line if node.coord else None
        self.symbols.append(
            {
                "name": node.name,
                "qualified_name": f"enum {node.name}",
                "kind": "c_enum",
                "line": line,
                "path": self._file_path,
                "signature": f"enum {node.name}",
                "doc_summary": "",
            }
        )


def _clean_c_source(source: str) -> str:
    """Strip preprocessor lines to improve parser compatibility for smoke indexing."""
    return "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))


def _record_skip(skipped_files: list[dict[str, str]] | None, relative_path: str, reason: str) -> None:
    """Append a normalized skipped-file record."""
    if skipped_files is None:
        return
    skipped_files.append({"path": relative_path, "stage": "c_symbols", "reason": reason})


def _process_single_c_file(
    path: Path,
    repo_root: Path,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    local_skipped: list[dict[str, str]] = []
    symbols: list[dict[str, object]] = []
    relative = path.relative_to(repo_root).as_posix()
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            _record_skip(local_skipped, relative_path=relative, reason="skip_large_file")
            return [], local_skipped
    except OSError:
        pass
    try:
        # CParser is instantiated inside the worker function to ensure thread-safety.
        parser = c_parser.CParser()
        source = _clean_c_source(path.read_text(encoding="utf-8"))
        tree = parser.parse(source, filename=relative)
        visitor = _SymbolVisitor(relative)
        visitor.visit(tree)
        symbols = visitor.symbols
    except Exception as exc:
        _record_skip(local_skipped, relative_path=relative, reason=f"parse_error:{exc.__class__.__name__}")
    return symbols, local_skipped


def index_c_symbols(
    repo_root: Path,
    skipped_files: list[dict[str, str]] | None = None,
    thread_count: int = 4,
) -> list[dict[str, object]]:
    """Index symbols from .c and .h files under repo_root."""
    paths: list[Path] = []
    excluded = {".git", ".venv", "__pycache__", "build", "tests"}
    import os
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in (".c", ".h"):
                paths.append(Path(root) / file)

    from concurrent.futures import ProcessPoolExecutor

    symbols: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=max(1, thread_count)) as executor:
        results = executor.map(_process_single_c_file, paths, [repo_root]*len(paths))
        for file_symbols, local_skipped in results:
            try:
                symbols.extend(file_symbols)
                if skipped_files is not None:
                    skipped_files.extend(local_skipped)
            except Exception:
                pass

    return symbols
