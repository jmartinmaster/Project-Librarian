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
"""Python symbol indexing using the standard library AST parser."""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

try:
    import libcst as cst
    from libcst.metadata import PositionProvider
except ImportError:
    cst = None
    PositionProvider = None


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


def _decorator_text_ast(node: ast.expr) -> str:
    """Return normalized string representation for an AST decorator node."""
    try:
        return ast.unparse(node).strip()
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{_decorator_text_ast(node.value)}.{node.attr}"
        return ""


def _module_symbols(
    path: Path,
    repo_root: Path,
    skipped_files: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Extract class and function symbols from one Python file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        # Indexed files are arbitrary third-party source (not our own code),
        # so invalid-escape-sequence SyntaxWarnings they trigger during
        # parsing are expected noise, not something the user can act on.
        # Suppress them here to avoid flooding the terminal while scanning
        # a large workspace.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except OSError as exc:
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason=f"read_error:{exc.__class__.__name__}")
        return []
    except SyntaxError:
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason="syntax_error")
        return []
    except Exception as exc:
        # A single malformed or unusual file (e.g. one that trips a rare
        # ValueError/RecursionError in the parser) must never abort the
        # whole workspace scan. Skip just this file and keep going.
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason=f"parse_error:{exc.__class__.__name__}")
        return []

    try:
        symbols = _extract_module_symbols(tree, path=path, repo_root=repo_root)
    except Exception as exc:
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason=f"symbol_error:{exc.__class__.__name__}")
        return []
    return symbols


def _extract_module_symbols(tree: ast.Module, path: Path, repo_root: Path) -> list[dict[str, object]]:
    """Walk a parsed module's top-level body and collect class/function symbols."""
    symbols: list[dict[str, object]] = []
    relative_path = path.relative_to(repo_root).as_posix()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_decorators = [_decorator_text_ast(d) for d in getattr(node, "decorator_list", []) if _decorator_text_ast(d)]
            symbols.append(
                {
                    "name": node.name,
                    "qualified_name": node.name,
                    "kind": "class",
                    "line": node.lineno,
                    "path": relative_path,
                    "signature": node.name,
                    "doc_summary": (ast.get_docstring(node) or "").splitlines()[0:1][0] if ast.get_docstring(node) else "",
                    "decorators": class_decorators,
                }
            )
            for class_node in node.body:
                if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qn = f"{node.name}.{class_node.name}"
                    func_decorators = [_decorator_text_ast(d) for d in getattr(class_node, "decorator_list", []) if _decorator_text_ast(d)]
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
                            "decorators": func_decorators,
                        }
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_decorators = [_decorator_text_ast(d) for d in getattr(node, "decorator_list", []) if _decorator_text_ast(d)]
            symbols.append(
                {
                    "name": node.name,
                    "qualified_name": node.name,
                    "kind": "function",
                    "line": node.lineno,
                    "path": relative_path,
                    "signature": _function_signature(node),
                    "doc_summary": (ast.get_docstring(node) or "").splitlines()[0:1][0] if ast.get_docstring(node) else "",
                    "decorators": func_decorators,
                }
            )
    return symbols


_BaseVisitor = cst.CSTVisitor if cst is not None else object
_PositionProvider = PositionProvider if PositionProvider is not None else object


def _cst_decorator_name(node: cst.Decorator) -> str:
    """Extract decorator name text from a libcst Decorator node."""
    try:
        import libcst as cst_mod
        dec_expr = node.decorator
        if isinstance(dec_expr, cst_mod.Call):
            dec_expr = dec_expr.func
        if isinstance(dec_expr, cst_mod.Name):
            return dec_expr.value
        if isinstance(dec_expr, cst_mod.Attribute):
            parts = []
            curr = dec_expr
            while isinstance(curr, cst_mod.Attribute):
                parts.append(curr.attr.value)
                curr = curr.value
            if isinstance(curr, cst_mod.Name):
                parts.append(curr.value)
            return ".".join(reversed(parts))
    except Exception:
        pass
    return ""


class _CSTSymbolVisitor(_BaseVisitor):
    METADATA_DEPENDENCIES = (_PositionProvider,) if PositionProvider is not None else ()

    def __init__(self, relative_path: str) -> None:
        super().__init__()
        self.relative_path = relative_path
        self.symbols: list[dict[str, object]] = []
        self.current_class: str | None = None

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        pos = self.get_metadata(PositionProvider, node)
        docstring = node.get_docstring() or ""
        doc_summary = docstring.strip().splitlines()[0].strip() if docstring else ""
        decorators = [_cst_decorator_name(d) for d in getattr(node, "decorators", []) if _cst_decorator_name(d)]
        start_line = pos.start.line
        if node.decorators:
            try:
                dec_pos = self.get_metadata(PositionProvider, node.decorators[0])
                start_line = min(start_line, dec_pos.start.line)
            except Exception:
                pass
        self.symbols.append(
            {
                "name": node.name.value,
                "qualified_name": node.name.value,
                "kind": "class",
                "line": start_line,
                "end_line": pos.end.line,
                "path": self.relative_path,
                "signature": node.name.value,
                "doc_summary": doc_summary,
                "decorators": decorators,
            }
        )
        self.current_class = node.name.value
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self.current_class = None

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        pos = self.get_metadata(PositionProvider, node)
        docstring = node.get_docstring() or ""
        doc_summary = docstring.strip().splitlines()[0].strip() if docstring else ""
        
        arg_names = []
        for param in node.params.params:
            arg_names.append(param.name.value)
        sig = f"{node.name.value}({', '.join(arg_names)})"

        if self.current_class:
            kind = "method"
            qualified_name = f"{self.current_class}.{node.name.value}"
        else:
            kind = "function"
            qualified_name = node.name.value

        decorators = [_cst_decorator_name(d) for d in getattr(node, "decorators", []) if _cst_decorator_name(d)]
        start_line = pos.start.line
        if node.decorators:
            try:
                dec_pos = self.get_metadata(PositionProvider, node.decorators[0])
                start_line = min(start_line, dec_pos.start.line)
            except Exception:
                pass
        self.symbols.append(
            {
                "name": node.name.value,
                "qualified_name": qualified_name,
                "kind": kind,
                "line": start_line,
                "end_line": pos.end.line,
                "path": self.relative_path,
                "signature": sig,
                "doc_summary": doc_summary,
                "decorators": decorators,
            }
        )
        return False


def _module_symbols_cst(
    path: Path,
    repo_root: Path,
    skipped_files: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Extract class and function symbols from one Python file using libcst."""
    import libcst as cst
    from libcst.metadata import MetadataWrapper, PositionProvider

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            module = cst.parse_module(source)
        wrapper = MetadataWrapper(module)
        relative_path = path.relative_to(repo_root).as_posix()
        visitor = _CSTSymbolVisitor(relative_path)
        wrapper.visit(visitor)
        return visitor.symbols
    except Exception as exc:
        _record_skip(skipped_files, path=path, repo_root=repo_root, reason=f"cst_error:{exc.__class__.__name__}")
        return []


def _process_single_python_file(
    path: Path,
    repo_root: Path,
    use_cst: bool,
    cst_max_file_size_kb: int = 200,
    cst_excluded_paths: list[str] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    local_skipped: list[dict[str, str]] = []
    try:
        try:
            file_size = path.stat().st_size
            if file_size > 5 * 1024 * 1024:
                _record_skip(local_skipped, path=path, repo_root=repo_root, reason="skip_large_file")
                return [], local_skipped
        except OSError:
            file_size = 0

        # CST File-size guard and exclusion checks
        effective_use_cst = use_cst
        if effective_use_cst:
            try:
                rel_path = path.relative_to(repo_root).as_posix()
            except ValueError:
                rel_path = path.as_posix()

            if file_size > cst_max_file_size_kb * 1024:
                effective_use_cst = False
            elif cst_excluded_paths:
                for excl in cst_excluded_paths:
                    cleaned = excl.strip().replace("\\", "/").strip("/")
                    if cleaned and (cleaned in rel_path or rel_path.startswith(cleaned)):
                        effective_use_cst = False
                        break

        if effective_use_cst:
            symbols = _module_symbols_cst(path=path, repo_root=repo_root, skipped_files=local_skipped)
        else:
            symbols = _module_symbols(path=path, repo_root=repo_root, skipped_files=local_skipped)
        return symbols, local_skipped
    except Exception as exc:
        _record_skip(local_skipped, path=path, repo_root=repo_root, reason=f"unexpected_error:{exc.__class__.__name__}")
        return [], local_skipped


def index_python_symbols(
    repo_root: Path,
    skipped_files: list[dict[str, str]] | None = None,
    use_cst: bool = True,
    thread_count: int = 4,
    excluded_dirs: list[str] | set[str] | None = None,
    cst_max_file_size_kb: int = 200,
    cst_excluded_paths: list[str] | None = None,
    cached_symbols: list[dict[str, object]] | None = None,
    cached_signatures: dict[str, tuple[float, int]] | None = None,
) -> list[dict[str, object]]:
    """Index Python symbols for all source files beneath repo_root."""
    if use_cst:
        try:
            import libcst as cst
            from libcst.metadata import PositionProvider
        except ImportError:
            use_cst = False
            if skipped_files is not None:
                skipped_files.append({
                    "path": "",
                    "stage": "python_symbols",
                    "reason": "libcst_missing_fallback_to_ast",
                })

    paths: list[Path] = []
    default_excluded = {".git", ".venv", "__pycache__", "build", "tests"}
    excluded = default_excluded.union(excluded_dirs) if excluded_dirs else default_excluded
    import os
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
        for file in files:
            if file.endswith(".py"):
                paths.append(Path(root) / file)

    retained_symbols: list[dict[str, object]] = []
    paths_to_process: list[Path] = []

    if cached_signatures is not None and cached_symbols is not None:
        cached_by_file: dict[str, list[dict[str, object]]] = {}
        for sym in cached_symbols:
            p = str(sym.get("path", ""))
            cached_by_file.setdefault(p, []).append(sym)

        for path in paths:
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                rel = path.as_posix()
            try:
                st = path.stat()
                sig = (st.st_mtime, st.st_size)
            except OSError:
                paths_to_process.append(path)
                continue

            if rel in cached_signatures and cached_signatures[rel] == sig and rel in cached_by_file:
                retained_symbols.extend(cached_by_file[rel])
            else:
                paths_to_process.append(path)
    else:
        paths_to_process = paths

    if not paths_to_process:
        return retained_symbols

    from concurrent.futures import ProcessPoolExecutor

    symbols: list[dict[str, object]] = list(retained_symbols)
    with ProcessPoolExecutor(max_workers=max(1, thread_count)) as executor:
        futures = [
            executor.submit(
                _process_single_python_file,
                path,
                repo_root,
                use_cst,
                cst_max_file_size_kb,
                cst_excluded_paths,
            )
            for path in paths_to_process
        ]
        for path, future in zip(paths_to_process, futures):
            try:
                file_symbols, local_skipped = future.result()
            except Exception as exc:
                if skipped_files is not None:
                    _record_skip(skipped_files, path=path, repo_root=repo_root, reason=f"worker_error:{exc.__class__.__name__}")
                continue
            symbols.extend(file_symbols)
            if skipped_files is not None:
                skipped_files.extend(local_skipped)

    return symbols

