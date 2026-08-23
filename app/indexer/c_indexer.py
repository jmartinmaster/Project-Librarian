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
"""C & C++ symbol indexing engine supporting headers, sources, classes, structs, functions, and macros."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pycparser import c_ast, c_parser

C_CPP_EXTENSIONS = {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx", ".ino"}


class _SymbolVisitor(c_ast.NodeVisitor):
    """Collect top-level C symbols from a parsed pycparser AST."""

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
    """Strip preprocessor lines to improve pycparser AST compatibility."""
    return "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))


def _extract_preceding_doc(lines: list[str], target_line_idx: int) -> str:
    """Extract single-line or multi-line comment summary directly preceding a line."""
    doc_lines = []
    idx = target_line_idx - 1
    while idx >= 0:
        raw = lines[idx].strip()
        if not raw:
            idx -= 1
            continue
        if raw.startswith("//"):
            doc_lines.insert(0, raw.lstrip("/ ").strip())
            idx -= 1
        elif raw.endswith("*/"):
            # backtrack to /*
            while idx >= 0:
                cur = lines[idx].strip()
                cleaned = cur.replace("/*", "").replace("*/", "").lstrip("* ").strip()
                if cleaned:
                    doc_lines.insert(0, cleaned)
                if "/*" in cur:
                    break
                idx -= 1
            break
        else:
            break
    return " ".join(doc_lines).strip()


def _extract_c_cpp_symbols_regex(source: str, relative_path: str) -> list[dict[str, Any]]:
    """Extract C and C++ symbols (functions, methods, classes, structs, enums, typedefs, macros)."""
    symbols: list[dict[str, Any]] = []
    lines = source.splitlines()

    # 1. Macros & Constants: #define NAME [(params)] [value]
    macro_pattern = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)(?:\(([^\)]*)\))?(?:\s+(.*))?$")
    for i, line in enumerate(lines):
        m = macro_pattern.match(line)
        if m:
            name = m.group(1)
            # Skip include guard macro patterns
            if name.startswith("_") and name.endswith("_H") or name.endswith("_H_"):
                continue
            params = m.group(2)
            sig = f"#define {name}({params})" if params is not None else f"#define {name}"
            doc = _extract_preceding_doc(lines, i)
            symbols.append({
                "name": name,
                "qualified_name": name,
                "kind": "c_macro",
                "line": i + 1,
                "path": relative_path,
                "signature": sig,
                "doc_summary": doc,
            })

    # 2. Structs, Unions, & Enums: struct/union/enum Name { ... }
    type_pattern = re.compile(r"\b(struct|union|enum)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\{;]")
    for i, line in enumerate(lines):
        for m in type_pattern.finditer(line):
            kind_str, name = m.group(1), m.group(2)
            doc = _extract_preceding_doc(lines, i)
            symbols.append({
                "name": name,
                "qualified_name": f"{kind_str} {name}",
                "kind": f"c_{kind_str}",
                "line": i + 1,
                "path": relative_path,
                "signature": f"{kind_str} {name}",
                "doc_summary": doc,
            })

    # 3. Typedef Structs / Types: typedef struct { ... } Name; or typedef int Name_t;
    typedef_pattern = re.compile(r"(?:\}\s*|\btypedef\s+[A-Za-z0-9_\*\s]+\s+)([A-Za-z_][A-Za-z0-9_]*)\s*;")
    for i, line in enumerate(lines):
        m = typedef_pattern.search(line)
        if m:
            name = m.group(1)
            if name not in {"int", "void", "char", "float", "double", "bool"}:
                doc = _extract_preceding_doc(lines, i)
                symbols.append({
                    "name": name,
                    "qualified_name": f"typedef {name}",
                    "kind": "c_typedef",
                    "line": i + 1,
                    "path": relative_path,
                    "signature": f"typedef {name}",
                    "doc_summary": doc,
                })

    # 4. C++ Classes & Namespaces: class Name : public Base {
    class_pattern = re.compile(r"\b(class|namespace)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*:\s*[^{]+)?\s*\{")
    for i, line in enumerate(lines):
        m = class_pattern.search(line)
        if m:
            kind_str, name = m.group(1), m.group(2)
            kind = "cpp_class" if kind_str == "class" else "cpp_namespace"
            doc = _extract_preceding_doc(lines, i)
            symbols.append({
                "name": name,
                "qualified_name": f"{kind_str} {name}",
                "kind": kind,
                "line": i + 1,
                "path": relative_path,
                "signature": f"{kind_str} {name}",
                "doc_summary": doc,
            })

    # 5. Functions & Methods: return_type [Class::]func(args) [{;]
    func_pattern = re.compile(
        r"^(?:\s*(?:static|inline|virtual|extern|constexpr|const|void|int|char|float|double|bool|uint[0-9]+_t|int[0-9]+_t|size_t|mp_obj_t|mp_uint_t|[A-Za-z_][A-Za-z0-9_]*[\s\*]+)+)"
        r"\s+([A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)?)\s*\(([^;\{]*)\)\s*(?:const)?\s*[\{;]",
        re.MULTILINE
    )
    for m in func_pattern.finditer(source):
        full_name = m.group(1)
        params = re.sub(r"\s+", " ", m.group(2).strip())
        line_num = source[:m.start()].count("\n") + 1
        name = full_name.split("::")[-1]
        kind = "cpp_method" if "::" in full_name else "c_function"
        doc = _extract_preceding_doc(lines, line_num - 1)
        symbols.append({
            "name": name,
            "qualified_name": full_name,
            "kind": kind,
            "line": line_num,
            "path": relative_path,
            "signature": f"{full_name}({params})",
            "doc_summary": doc,
        })

    # Deduplicate symbols by (kind, qualified_name, line)
    seen = set()
    deduped = []
    for s in symbols:
        key = (s.get("kind"), s.get("qualified_name"), s.get("line"))
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped


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

    content = ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        _record_skip(local_skipped, relative_path=relative, reason=f"read_error:{exc.__class__.__name__}")
        return [], local_skipped

    # 1. First attempt fast, comprehensive regex extraction
    regex_symbols = _extract_c_cpp_symbols_regex(content, relative)

    # 2. Try pycparser on pure C files if regex found nothing or for deeper verification
    if not regex_symbols and path.suffix.lower() == ".c":
        try:
            parser = c_parser.CParser()
            source = _clean_c_source(content)
            tree = parser.parse(source, filename=relative)
            visitor = _SymbolVisitor(relative)
            visitor.visit(tree)
            symbols = visitor.symbols
        except Exception:
            pass

    symbols = regex_symbols or symbols
    return symbols, local_skipped


def index_c_symbols(
    repo_root: Path,
    skipped_files: list[dict[str, str]] | None = None,
    thread_count: int = 4,
) -> list[dict[str, object]]:
    """Index symbols from C & C++ source and header files under repo_root."""
    paths: list[Path] = []
    excluded = {".git", ".venv", "__pycache__", "build", "tests"}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in C_CPP_EXTENSIONS:
                paths.append(Path(root) / file)

    from concurrent.futures import ProcessPoolExecutor

    symbols: list[dict[str, object]] = []
    if not paths:
        return symbols

    with ProcessPoolExecutor(max_workers=max(1, min(thread_count, len(paths)))) as executor:
        results = executor.map(_process_single_c_file, paths, [repo_root] * len(paths))
        for file_symbols, local_skipped in results:
            try:
                symbols.extend(file_symbols)
                if skipped_files is not None:
                    skipped_files.extend(local_skipped)
            except Exception:
                pass

    return symbols
