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
"""Standalone MCP-compatible server for Project Librarian state using FastAPI."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import signal
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import libcst as cst
import libcst.metadata as metadata
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, Query, Header, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pycparser import c_ast, c_parser
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        from mcp.server import MCPServer as FastMCP

from app.config import load_config
from app.indexer.index_manager import IndexManager
from app.search.search_engine import search_snapshot
from app.controllers.anti_pattern_controller import AntiPatternController
from app.models.web_dashboard import get_web_dashboard_html

AUTH_HEADER_NAME = "X-The-Librarian-Token"

# Global managers initialized during setup
manager: IndexManager | None = None
auth_token: str = ""


# --- AST / CST Parsing Engines ---

class PythonCSTVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.PositionProvider,)

    def __init__(self) -> None:
        self.classes = []
        self.functions = []
        self.imports = []
        self.variables = []
        self._current_class = None

    def _get_docstring(self, node: Any) -> str:
        docstring = ""
        if node.body and isinstance(node.body, cst.IndentedBlock):
            if node.body.body:
                first_stmt = node.body.body[0]
                if isinstance(first_stmt, cst.SimpleStatementLine) and first_stmt.body:
                    expr = first_stmt.body[0]
                    if isinstance(expr, cst.Expr) and isinstance(expr.value, cst.SimpleString):
                        try:
                            import ast as py_ast
                            docstring = py_ast.literal_eval(expr.value.value)
                        except Exception:
                            docstring = expr.value.value
        return docstring

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        pos = self.get_metadata(metadata.PositionProvider, node)
        cls_info = {
            "name": node.name.value,
            "start_line": pos.start.line,
            "end_line": pos.end.line,
            "methods": [],
            "docstring": self._get_docstring(node)
        }
        self.classes.append(cls_info)
        self._current_class = cls_info
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self._current_class = None

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        pos = self.get_metadata(metadata.PositionProvider, node)
        arg_names = []
        for p in node.params.params:
            arg_names.append(p.name.value)
        if isinstance(node.params.star_arg, cst.Param) and node.params.star_arg.name:
            name_val = node.params.star_arg.name.value if hasattr(node.params.star_arg.name, "value") else node.params.star_arg.name
            arg_names.append(f"*{name_val}")
        for p in node.params.kwonly_params:
            arg_names.append(p.name.value)
        if isinstance(node.params.star_kwarg, cst.Param) and node.params.star_kwarg.name:
            name_val = node.params.star_kwarg.name.value if hasattr(node.params.star_kwarg.name, "value") else node.params.star_kwarg.name
            arg_names.append(f"**{name_val}")

        sig = f"{node.name.value}({', '.join(arg_names)})"
        func_info = {
            "name": node.name.value,
            "start_line": pos.start.line,
            "end_line": pos.end.line,
            "signature": sig,
            "docstring": self._get_docstring(node)
        }
        if self._current_class:
            self._current_class["methods"].append(func_info)
        else:
            self.functions.append(func_info)
        return False

    def visit_Import(self, node: cst.Import) -> bool:
        pos = self.get_metadata(metadata.PositionProvider, node)
        for alias in node.names:
            asname = alias.asname.name.value if alias.asname and hasattr(alias.asname, "name") else ""
            name_val = self._get_name_value(alias.name)
            self.imports.append({
                "name": name_val,
                "asname": asname,
                "line": pos.start.line
            })
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        pos = self.get_metadata(metadata.PositionProvider, node)
        module = self._get_name_value(node.module) if node.module else ""
        dots = ""
        if node.relative:
            for dot in node.relative:
                dots += "."
        full_module = dots + module

        if isinstance(node.names, cst.ImportStar):
            self.imports.append({
                "name": f"{full_module}.*",
                "asname": "",
                "line": pos.start.line
            })
        else:
            for alias in node.names:
                asname = alias.asname.name.value if alias.asname and hasattr(alias.asname, "name") else ""
                import_name = alias.name.value
                self.imports.append({
                    "name": f"{full_module}.{import_name}" if full_module else import_name,
                    "asname": asname,
                    "line": pos.start.line
                })
        return False

    def visit_Assign(self, node: cst.Assign) -> bool:
        pos = self.get_metadata(metadata.PositionProvider, node)
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                self.variables.append({
                    "name": target.target.value,
                    "line": pos.start.line
                })
        return False

    def _get_name_value(self, node: Any) -> str:
        if isinstance(node, cst.Name):
            return node.value
        elif isinstance(node, cst.Attribute):
            return f"{self._get_name_value(node.value)}.{node.attr.value}"
        return ""


class CFileVisitor(c_ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions = []
        self.structs = []
        self.enums = []

    def visit_FuncDef(self, node: c_ast.FuncDef) -> None:
        decl = node.decl
        line = decl.coord.line if decl.coord else 1
        self.functions.append({
            "name": decl.name,
            "start_line": line,
            "end_line": line,
            "signature": decl.name,
            "docstring": ""
        })

    def visit_Struct(self, node: c_ast.Struct) -> None:
        if not node.name:
            return
        line = node.coord.line if node.coord else 1
        self.structs.append({
            "name": node.name,
            "start_line": line,
            "end_line": line
        })

    def visit_Enum(self, node: c_ast.Enum) -> None:
        if not node.name:
            return
        line = node.coord.line if node.coord else 1
        self.enums.append({
            "name": node.name,
            "start_line": line,
            "end_line": line
        })


def _clean_c_source(source: str) -> str:
    """Strip preprocessor lines to improve parser compatibility for C indexing."""
    return "\n".join(line for line in source.splitlines() if not line.strip().startswith("#"))


def _get_file_ast_cst_python_fallback(rel_path: str, source: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except Exception as exc:
        return {"error": f"Failed to parse Python file: {str(exc)}"}

    classes = []
    functions = []
    imports = []
    assignments = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = []
            for subnode in node.body:
                if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    arg_names = [arg.arg for arg in subnode.args.args]
                    methods.append({
                        "name": subnode.name,
                        "start_line": subnode.lineno,
                        "end_line": getattr(subnode, "end_lineno", subnode.lineno),
                        "signature": f"{subnode.name}({', '.join(arg_names)})",
                        "docstring": ast.get_docstring(subnode) or ""
                    })
            classes.append({
                "name": node.name,
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "methods": methods,
                "docstring": ast.get_docstring(node) or ""
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arg_names = [arg.arg for arg in node.args.args]
            functions.append({
                "name": node.name,
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "signature": f"{node.name}({', '.join(arg_names)})",
                "docstring": ast.get_docstring(node) or ""
            })
        elif isinstance(node, ast.Import):
            for name in node.names:
                imports.append({
                    "name": name.name,
                    "asname": name.asname or "",
                    "line": node.lineno
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for name in node.names:
                imports.append({
                    "name": f"{module}.{name.name}" if module else name.name,
                    "asname": name.asname or "",
                    "line": node.lineno
                })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.append({
                        "name": target.id,
                        "line": node.lineno
                    })

    return {
        "path": rel_path,
        "language": "python",
        "classes": classes,
        "functions": functions,
        "imports": imports,
        "variables": assignments
    }


def _get_file_ast_cst(repo_root: Path, rel_path: str) -> dict[str, Any] | None:
    path = (repo_root / rel_path).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None

    ext = path.suffix.lower()
    if ext == ".py":
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = cst.parse_module(source)
            wrapper = metadata.MetadataWrapper(tree)
            visitor = PythonCSTVisitor()
            wrapper.visit(visitor)
            return {
                "path": rel_path,
                "language": "python",
                "classes": visitor.classes,
                "functions": visitor.functions,
                "imports": visitor.imports,
                "variables": visitor.variables
            }
        except Exception:
            # Fallback to standard Python AST
            return _get_file_ast_cst_python_fallback(rel_path, source)
    elif ext in {".c", ".h"}:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return {"error": f"Failed to read C file: {str(exc)}"}

        try:
            cleaned = _clean_c_source(source)
            parser = c_parser.CParser()
            tree = parser.parse(cleaned, filename=rel_path)
            visitor = CFileVisitor()
            visitor.visit(tree)
            return {
                "path": rel_path,
                "language": "c",
                "classes": visitor.structs,
                "functions": visitor.functions,
                "enums": visitor.enums,
                "imports": []
            }
        except Exception:
            # Fallback to legacy regex search
            functions = []
            structs = []
            enums = []

            func_pat = re.compile(r"^\s*(?:[a-zA-Z_][a-zA-Z0-9_*]*\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{?", re.MULTILINE)
            struct_pat = re.compile(r"^\s*struct\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE)
            enum_pat = re.compile(r"^\s*enum\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE)

            for line_num, line in enumerate(source.splitlines(), start=1):
                f_match = func_pat.match(line)
                if f_match and not any(k in line for k in {"if", "while", "for", "switch", "return"}):
                    name = f_match.group(1)
                    functions.append({"name": name, "start_line": line_num, "end_line": line_num})
                s_match = struct_pat.match(line)
                if s_match:
                    structs.append({"name": s_match.group(1), "start_line": line_num, "end_line": line_num})
                e_match = enum_pat.match(line)
                if e_match:
                    enums.append({"name": e_match.group(1), "start_line": line_num, "end_line": line_num})

            return {
                "path": rel_path,
                "language": "c",
                "classes": structs,
                "functions": functions,
                "enums": enums,
                "imports": []
            }

    return {"error": f"Unsupported file type: {ext}"}


def _build_probe_payload(host: str, port: int, token_required: bool) -> dict[str, object]:
    base = f"http://{host}:{port}"
    return {
        "status": "ok",
        "server": "Project Librarian",
        "auth_required": token_required,
        "transport_configured": "streamable-http",
        "endpoints": {
            "probe": f"{base}/api/mcp-probe",
            "probe_jsonrpc": f"{base}/api/mcp-probe/jsonrpc",
            "status": f"{base}/api/status",
            "search": f"{base}/api/search",
            "ast": f"{base}/api/ast",
            "cst": f"{base}/api/cst",
            "refresh": f"{base}/api/server/refresh",
            "shutdown": f"{base}/api/server/shutdown",
            "sse": f"{base}/sse",
            "mcp_sse": f"{base}/mcp/sse",
            "messages": f"{base}/messages",
            "mcp_messages": f"{base}/mcp/messages",
        },
        "auth": {"accepted": ["Authorization: Bearer <token>", f"{AUTH_HEADER_NAME}: <token>", "?token=<token>"]},
    }


def audit_mvc_triads(repo_root: Path) -> dict[str, Any]:
    py_files = []
    for path in repo_root.rglob("*.py"):
        if any(part in path.parts for part in {".git", ".venv", "build", "tests", "__pycache__"}):
            continue
        py_files.append(path.resolve())

    triads = {}

    for f in py_files:
        filename = f.name
        dirname = f.parent
        name, _ = os.path.splitext(filename)

        parent_dir_name = dirname.name.lower()
        if parent_dir_name in ("models", "model", "views", "view", "controllers", "controller"):
            core_name = name
            for suffix in ("_model", "_view", "_controller", "model", "view", "controller"):
                if core_name.lower().endswith(suffix):
                    core_name = core_name[:-len(suffix)]
                    if core_name.endswith("_"):
                        core_name = core_name[:-1]
                    break
            grand_parent = dirname.parent
            key = f"{grand_parent.as_posix()}:{core_name}"
            if key not in triads:
                triads[key] = {"name": core_name, "directory": grand_parent.as_posix(), "model": None, "view": None, "controller": None}

            if parent_dir_name in ("models", "model"):
                triads[key]["model"] = f.as_posix()
            elif parent_dir_name in ("views", "view"):
                triads[key]["view"] = f.as_posix()
            elif parent_dir_name in ("controllers", "controller"):
                triads[key]["controller"] = f.as_posix()

        else:
            is_mvc_suffix = False
            core_name = name
            role = None
            for suffix in ("_model", "_view", "_controller"):
                if name.lower().endswith(suffix):
                    core_name = name[:-len(suffix)]
                    is_mvc_suffix = True
                    role = suffix[1:]
                    break
            if is_mvc_suffix:
                key = f"{dirname.as_posix()}:{core_name}"
                if key not in triads:
                    triads[key] = {"name": core_name, "directory": dirname.as_posix(), "model": None, "view": None, "controller": None}
                triads[key][role] = f.as_posix()

    complete = []
    incomplete = []
    for t in triads.values():
        if t["model"] and t["view"] and t["controller"]:
            complete.append(t)
        else:
            incomplete.append(t)

    return {
        "complete_count": len(complete),
        "incomplete_count": len(incomplete),
        "complete_triads": complete,
        "incomplete_triads": incomplete
    }


# --- FastMCP Server Definition ---

mcp = FastMCP("Project Librarian")


@mcp.tool()
def search_codebase(query: str, scope: str = "all", limit: int = 20) -> str:
    """Search the codebase for files, symbols, or excel rows.

    Args:
        query: Search query string.
        scope: Search scope ('all', 'files', 'symbols', 'excel_rows').
        limit: Max number of results (default 20, max 200).
    """
    global manager
    if not manager:
        return json.dumps({"error": "Index manager not initialized"})

    results = search_snapshot(
        file_corpus=manager.state.file_corpus,
        symbols=manager.state.symbols,
        excel_rows=manager.state.excel_rows,
        query=query,
        scope=scope,
        limit=max(1, min(limit, 200)),
    )
    return json.dumps(results)


@mcp.resource("file:///{relative_path}")
def inspect_file(relative_path: str) -> str:
    """Inspect text content and structural AST/CST metadata of a specific file.

    Args:
        relative_path: Relative path to the file from the project root.
    """
    global manager
    if not manager:
        return json.dumps({"error": "Index manager not initialized"})

    import urllib.parse
    relative_path = urllib.parse.unquote(relative_path)

    repo_root = Path(manager.config.project_root)
    file_path = (repo_root / relative_path).resolve()
    try:
        file_path.relative_to(repo_root)
    except ValueError:
        return json.dumps({"error": "Path outside repository root"})

    if not file_path.exists() or not file_path.is_file():
        return json.dumps({"error": "File not found"})

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e}"})

    structure = _get_file_ast_cst(repo_root, relative_path)
    return json.dumps({
        "content": content,
        "structure": structure
    })


@mcp.tool()
def audit_triad(scope: str = "all", filter_text: str = "") -> str:
    """Audit the codebase for MVC component triads and scan for anti-patterns.

    Args:
        scope: Scan scope ('all' or 'changed').
        filter_text: Filename substring filter (optional).
    """
    global manager
    if not manager:
        return json.dumps({"error": "Index manager not initialized"})

    repo_root = Path(manager.config.project_root)
    mvc_report = audit_mvc_triads(repo_root)

    controller = AntiPatternController(index_manager=manager)
    presets = controller.load_presets()
    anti_pattern_matches = controller.run_scan(presets=presets, scope=scope, filter_text=filter_text)

    return json.dumps({
        "mvc_triads_report": mvc_report,
        "anti_pattern_matches": anti_pattern_matches
    })


@mcp.tool()
def generate_triad_boilerplate(model_path: str, view_path: str, controller_path: str) -> str:
    """Scan Model, View, and Controller files, call local AI (Ollama) to generate boilerplate,
    and propagate changes.
    """
    global manager
    if not manager:
        return json.dumps({"error": "Index manager not initialized"})
    repo_root = Path(manager.config.project_root)
    m_abs = Path(model_path)
    if not m_abs.is_absolute():
        m_abs = repo_root / model_path
    v_abs = Path(view_path)
    if not v_abs.is_absolute():
        v_abs = repo_root / view_path
    c_abs = Path(controller_path)
    if not c_abs.is_absolute():
        c_abs = repo_root / controller_path

    from app.models.ai_generator import AIGenerationService
    generator = AIGenerationService()
    ok, msg = generator.process_triad(str(m_abs.resolve()), str(v_abs.resolve()), str(c_abs.resolve()))
    return json.dumps({"success": ok, "message": msg})


@mcp.tool()
def get_call_graph(symbol: str) -> str:
    """Analyze references, callers, callees, and dependencies for a symbol across the codebase.

    Args:
        symbol: Function, class, struct, or macro name to trace.
    """
    global manager
    if not manager:
        return json.dumps({"error": "Index manager not initialized"})
    from app.indexer.call_graph import CallGraphEngine
    repo_root = Path(manager.config.project_root)
    graph = CallGraphEngine.analyze_symbol(
        repo_root=repo_root,
        symbol_name=symbol,
        symbols=manager.state.symbols,
        file_corpus=manager.state.file_corpus,
    )
    return json.dumps(graph)


# --- FastAPI Application ---

fastapi_app = FastAPI()


@fastapi_app.middleware("http")
async def auth_and_cors_middleware(request: Request, call_next: Any) -> Response:
    if request.method == "OPTIONS":
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

    if auth_token:
        auth_header = request.headers.get("authorization", "")
        req_token = ""
        if auth_header.lower().startswith("bearer "):
            req_token = auth_header[7:].strip()
        if not req_token:
            req_token = request.headers.get(AUTH_HEADER_NAME.lower(), "")
        if not req_token:
            req_token = request.query_params.get("token", "")

        if req_token != auth_token:
            res = JSONResponse(status_code=401, content={"error": "Unauthorized"})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res

    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@fastapi_app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    return HTMLResponse(content=get_web_dashboard_html(), status_code=200)


@fastapi_app.get("/")
@fastapi_app.get("/mcp")
@fastapi_app.get("/mcp/")
@fastapi_app.get("/api/mcp-probe")
async def get_probe(request: Request) -> Any:
    accept = request.headers.get("accept", "").lower()
    if "text/html" in accept:
        return HTMLResponse(content=get_web_dashboard_html(), status_code=200)
    host = request.url.hostname or "127.0.0.1"
    port = request.url.port or 8765
    return _build_probe_payload(host=host, port=port, token_required=bool(auth_token))


@fastapi_app.get("/api/status")
async def get_status() -> dict[str, Any]:
    global manager
    assert manager is not None
    status_payload = manager.refresh_status()
    status_payload["repo_root"] = str(Path(manager.config.project_root).resolve())
    status_payload["output_dir"] = str(Path(manager.config.output_dir))
    return status_payload


@fastapi_app.get("/api/search")
async def get_search(q: str = "", scope: str = "all", limit: int = 20) -> dict[str, Any]:
    global manager
    assert manager is not None
    results = search_snapshot(
        file_corpus=manager.state.file_corpus,
        symbols=manager.state.symbols,
        excel_rows=manager.state.excel_rows,
        query=q,
        scope=scope,
        limit=max(1, min(limit, 200)),
    )
    return {"count": len(results), "results": results}


@fastapi_app.post("/api/search")
async def post_search(payload: dict) -> dict[str, Any]:
    global manager
    assert manager is not None
    q = payload.get("q", "")
    scope = payload.get("scope", "all")
    limit = payload.get("limit", 20)
    results = search_snapshot(
        file_corpus=manager.state.file_corpus,
        symbols=manager.state.symbols,
        excel_rows=manager.state.excel_rows,
        query=q,
        scope=scope,
        limit=max(1, min(limit, 200)),
    )
    return {"count": len(results), "results": results}


@fastapi_app.get("/api/call-graph")
@fastapi_app.post("/api/call-graph")
async def get_call_graph_endpoint(symbol: str = "", payload: dict | None = None) -> dict[str, Any]:
    global manager
    assert manager is not None
    sym = symbol
    if not sym and payload and isinstance(payload, dict):
        sym = str(payload.get("symbol") or payload.get("q") or "").strip()
    from app.indexer.call_graph import CallGraphEngine
    repo_root = Path(manager.config.project_root)
    return CallGraphEngine.analyze_symbol(
        repo_root=repo_root,
        symbol_name=sym,
        symbols=manager.state.symbols,
        file_corpus=manager.state.file_corpus,
    )


@fastapi_app.get("/api/ast")
@fastapi_app.get("/api/cst")
async def get_ast(path: str) -> dict[str, Any]:
    global manager
    assert manager is not None
    repo_root = Path(manager.config.project_root)
    data = _get_file_ast_cst(repo_root, path)
    if data is None or "error" in data:
        raise HTTPException(status_code=404, detail=data.get("error") if data else "File not found")
    return data


@fastapi_app.post("/api/ast")
@fastapi_app.post("/api/cst")
async def post_ast(payload: dict) -> dict[str, Any]:
    global manager
    assert manager is not None
    rel_path = str(payload.get("path") or "").strip()
    if not rel_path:
        raise HTTPException(status_code=400, detail="Missing 'path' parameter")
    repo_root = Path(manager.config.project_root)
    data = _get_file_ast_cst(repo_root, rel_path)
    if data is None or "error" in data:
        raise HTTPException(status_code=404, detail=data.get("error") if data else "File not found")
    return data


@fastapi_app.post("/api/server/refresh")
async def post_refresh() -> dict[str, bool]:
    global manager
    assert manager is not None
    started = manager.request_refresh_async()
    return {"ok": True, "started": started}


@fastapi_app.post("/api/ai/generate")
async def post_ai_generate(payload: dict) -> dict[str, Any]:
    global manager
    assert manager is not None
    model_path = str(payload.get("model_path") or "").strip()
    view_path = str(payload.get("view_path") or "").strip()
    controller_path = str(payload.get("controller_path") or "").strip()

    if not model_path or not view_path or not controller_path:
        raise HTTPException(status_code=400, detail="Missing required path parameters ('model_path', 'view_path', 'controller_path')")

    repo_root = Path(manager.config.project_root)
    m_abs = Path(model_path)
    if not m_abs.is_absolute():
        m_abs = repo_root / model_path
    v_abs = Path(view_path)
    if not v_abs.is_absolute():
        v_abs = repo_root / view_path
    c_abs = Path(controller_path)
    if not c_abs.is_absolute():
        c_abs = repo_root / controller_path

    from app.models.ai_generator import AIGenerationService
    generator = AIGenerationService()
    ok, msg = generator.process_triad(str(m_abs.resolve()), str(v_abs.resolve()), str(c_abs.resolve()))
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


@fastapi_app.post("/api/server/shutdown")
async def post_shutdown(background_tasks: BackgroundTasks) -> dict[str, object]:
    def shutdown_server() -> None:
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)

    background_tasks.add_task(shutdown_server)
    return {"ok": True, "message": "Shutting down"}


@fastapi_app.post("/api/mcp-probe/jsonrpc")
async def jsonrpc_endpoint(request: Request, payload: dict) -> dict[str, Any]:
    global manager
    assert manager is not None
    request_id = payload.get("id")
    method = str(payload.get("method") or "").strip()

    if method in {"mcp.ping", "ping", "rpc.ping"}:
        return {"jsonrpc": "2.0", "id": request_id, "result": {"ok": True}}

    if method in {"mcp.probe", "probe", "rpc.discover"}:
        host = request.url.hostname or "127.0.0.1"
        port = request.url.port or 8765
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _build_probe_payload(host=host, port=port, token_required=bool(auth_token)),
        }

    if method in {"mcp.search", "search"}:
        params = payload.get("params") or {}
        query_term = str(params.get("q") or "").strip()
        scope = str(params.get("scope") or "all").strip()
        limit = int(params.get("limit") or 20)
        results = search_snapshot(
            file_corpus=manager.state.file_corpus,
            symbols=manager.state.symbols,
            excel_rows=manager.state.excel_rows,
            query=query_term,
            scope=scope,
            limit=max(1, min(limit, 200)),
        )
        return {"jsonrpc": "2.0", "id": request_id, "result": {"count": len(results), "results": results}}

    if method in {"mcp.ast", "ast", "mcp.cst", "cst"}:
        params = payload.get("params") or {}
        rel_path = str(params.get("path") or "").strip()
        if not rel_path:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "Missing 'path' parameter in params"},
            }
        repo_root = Path(manager.config.project_root)
        data = _get_file_ast_cst(repo_root, rel_path)
        if data is None or "error" in data:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": data.get("error") if data else "File not found"},
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": data}

    if method in {"mcp.call_graph", "call_graph", "call_hierarchy"}:
        params = payload.get("params") or {}
        symbol_name = str(params.get("symbol") or params.get("q") or "").strip()
        from app.indexer.call_graph import CallGraphEngine
        repo_root = Path(manager.config.project_root)
        graph = CallGraphEngine.analyze_symbol(
            repo_root=repo_root,
            symbol_name=symbol_name,
            symbols=manager.state.symbols,
            file_corpus=manager.state.file_corpus,
        )
        return {"jsonrpc": "2.0", "id": request_id, "result": graph}

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unsupported probe method: {method}"},
    }


def run_mcp_server(repo_root: str, output_dir: str, host: str, port: int, auth_token_val: str = "", transport: str = "sse") -> None:
    """Run MCP server under specified transport."""
    global manager, auth_token
    os.environ["THE_LIBRARIAN_IS_CHILD"] = "1"
    os.environ["THE_LIBRARIAN_NO_SUPERVISOR"] = "1"
    os.environ["THE_LIBRARIAN_MCP_SERVER"] = "1"
    app_root = str(Path(__file__).resolve().parents[2])
    pythonpath = os.environ.get("PYTHONPATH", "")
    if app_root not in pythonpath:
        os.environ["PYTHONPATH"] = f"{app_root}{os.pathsep}{pythonpath}" if pythonpath else app_root

    config = load_config()
    config.project_root = repo_root
    config.output_dir = output_dir
    manager = IndexManager(config=config)

    auth_token = auth_token_val.strip()

    # Determine transport mode
    transport_lower = transport.strip().lower()
    if transport_lower in {"stdio"}:
        # Standard stdio mode
        manager.start_refresh_worker(run_immediately=True)
        try:
            mcp.run(transport="stdio")
        finally:
            manager.stop_refresh_worker()
    else:
        # SSE / HTTP FastAPI mode
        # Mount the FastMCP HTTP app at /mcp
        mcp_app = mcp.sse_app()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            manager.start_refresh_worker(run_immediately=True)
            yield
            manager.stop_refresh_worker()

        fastapi_app.router.lifespan_context = lifespan

        # Mount FastMCP HTTP endpoints
        fastapi_app.mount("/mcp", mcp_app)
        fastapi_app.mount("/", mcp_app)

        uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Project Librarian MCP server")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", default="build")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="")
    parser.add_argument("--transport", default="sse")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_mcp_server(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        host=args.host,
        port=int(args.port),
        auth_token_val=args.token,
        transport=args.transport,
    )


if __name__ == "__main__":
    main()
