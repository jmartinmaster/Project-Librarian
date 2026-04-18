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


def index_c_symbols(repo_root: Path, skipped_files: list[dict[str, str]] | None = None) -> list[dict[str, object]]:
    """Index symbols from .c and .h files under repo_root."""
    parser = c_parser.CParser()
    symbols: list[dict[str, object]] = []
    for path in sorted(repo_root.rglob("*")):
        if path.suffix.lower() not in {".c", ".h"}:
            continue
        if "build" in path.parts or "tests" in path.parts:
            continue

        relative = path.relative_to(repo_root).as_posix()
        try:
            source = _clean_c_source(path.read_text(encoding="utf-8"))
            tree = parser.parse(source, filename=relative)
        except Exception as exc:
            _record_skip(skipped_files, relative_path=relative, reason=f"parse_error:{exc.__class__.__name__}")
            continue

        visitor = _SymbolVisitor(relative)
        visitor.visit(tree)
        symbols.extend(visitor.symbols)
    return symbols
