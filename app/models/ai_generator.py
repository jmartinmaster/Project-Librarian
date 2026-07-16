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
"""AI-driven code generation service for propagating boilerplate methods across MVC triads using code outlines (chunking)."""

from __future__ import annotations

import ast
import datetime
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


def get_file_outline(source: str) -> str:
    """Extract class/method names, signatures, and docstrings using AST parsing."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"[Syntax Error - Cannot Parse Outline: {e}]"

    outline_lines = []
    
    # List top level imports
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for name in node.names:
                    asname = f" as {name.asname}" if name.asname else ""
                    import_lines.append(f"import {name.name}{asname}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(name.name + (f" as {name.asname}" if name.asname else "") for name in node.names)
                import_lines.append(f"from {module} import {names}")
    
    if import_lines:
        outline_lines.append("# Imports:")
        outline_lines.extend(f"# {line}" for line in import_lines)
        outline_lines.append("")

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            outline_lines.append(f"class {node.name}:")
            doc = ast.get_docstring(node)
            if doc:
                outline_lines.append(f"    \"\"\"{doc}\"\"\"")
            
            methods_found = False
            for subnode in node.body:
                if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods_found = True
                    args = [arg.arg for arg in subnode.args.args]
                    sig = f"{subnode.name}({', '.join(args)})"
                    prefix = "async def " if isinstance(subnode, ast.AsyncFunctionDef) else "def "
                    
                    # Keep constructor and layout/ui methods intact to preserve widget/signal wiring names
                    keep_body = subnode.name == "__init__" or "ui" in subnode.name.lower() or "layout" in subnode.name.lower()
                    
                    if keep_body:
                        method_source = ast.get_source_segment(source, subnode)
                        if method_source:
                            indented_lines = []
                            for line in method_source.splitlines():
                                if line.strip():
                                    indented_lines.append("    " + line)
                                else:
                                    indented_lines.append("")
                            outline_lines.extend(indented_lines)
                        else:
                            outline_lines.append(f"    {prefix}{sig}: ...")
                    else:
                        outline_lines.append(f"    {prefix}{sig}: ...")
                        sub_doc = ast.get_docstring(subnode)
                        if sub_doc:
                            outline_lines.append(f"        \"\"\"{sub_doc}\"\"\"")
            if not methods_found:
                outline_lines.append("    pass")
            outline_lines.append("")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.args]
            sig = f"{node.name}({', '.join(args)})"
            prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            
            # Keep standalone layout/ui functions intact as well
            keep_body = "ui" in node.name.lower() or "layout" in node.name.lower()
            if keep_body:
                method_source = ast.get_source_segment(source, node)
                if method_source:
                    outline_lines.extend(method_source.splitlines())
                else:
                    outline_lines.append(f"{prefix}{sig}: ...")
            else:
                outline_lines.append(f"{prefix}{sig}: ...")
                doc = ast.get_docstring(node)
                if doc:
                    outline_lines.append(f"    \"\"\"{doc}\"\"\"")
            outline_lines.append("")
            
    return "\n".join(outline_lines).strip()


def find_primary_class(source: str) -> tuple[str | None, int | None]:
    """Find the first class defined in the source file, return its name and end_lineno."""
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                return node.name, getattr(node, "end_lineno", None)
    except Exception:
        pass
    return None, None


def replace_method_in_source(source: str, class_name: str, method_name: str, new_method_source: str) -> str | None:
    """Locate and replace an existing method body within a class in the source code using AST."""
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for subnode in node.body:
                    if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)) and subnode.name == method_name:
                        lines = source.splitlines()
                        start_idx = subnode.lineno - 1
                        end_idx = getattr(subnode, "end_lineno", subnode.lineno)
                        
                        new_lines = new_method_source.splitlines()
                        lines[start_idx:end_idx] = new_lines
                        return "\n".join(lines)
    except Exception:
        pass
    return None


def generate_method_code(method_dict: dict[str, Any]) -> str:
    """Generate clean Python method code (with pass) from metadata dictionary."""
    name = method_dict.get("name", "").strip()
    args = method_dict.get("args", "self").strip()
    decorator = method_dict.get("decorator", "").strip()
    docstring = method_dict.get("docstring", "").strip()
    
    if not name:
        return ""
        
    if "self" not in args and decorator not in ("classmethod", "staticmethod"):
        if args:
            args = "self, " + args
        else:
            args = "self"
            
    code_lines = []
    if decorator:
        code_lines.append(f"@{decorator}")
    code_lines.append(f"def {name}({args}):")
    if docstring:
        code_lines.append(f'    """{docstring}"""')
    code_lines.append("    pass")
    return "\n".join(code_lines)


def insert_signals_in_class(source: str, class_name: str, signals: list[str]) -> str:
    """Insert class-level signal declarations right after the class docstring or class header."""
    if not signals:
        return source
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                lines = source.splitlines()
                insert_idx = node.lineno
                
                if node.body:
                    first_sub = node.body[0]
                    if isinstance(first_sub, ast.Expr) and isinstance(first_sub.value, ast.Constant) and isinstance(first_sub.value.value, str):
                        insert_idx = getattr(first_sub, "end_lineno", first_sub.lineno)
                        
                signal_lines = []
                for sig in signals:
                    if sig.strip():
                        if sig.startswith("    "):
                            signal_lines.append(sig)
                        else:
                            signal_lines.append("    " + sig)
                
                lines.insert(insert_idx, "")
                for idx, sig_l in enumerate(signal_lines):
                    lines.insert(insert_idx + 1 + idx, sig_l)
                return "\n".join(lines)
    except Exception:
        pass
    return source


def custom_dedent(text: str) -> str:
    """Normalize tabs to 4 spaces, find the minimum leading space indentation of non-empty lines, and dedent."""
    text = text.replace("\t", "    ")
    lines = text.splitlines()
    
    min_indent = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        leading_spaces = len(line) - len(line.lstrip(' '))
        if min_indent is None or leading_spaces < min_indent:
            min_indent = leading_spaces
            
    if min_indent:
        dedented_lines = []
        for line in lines:
            if len(line) >= min_indent and line[:min_indent].strip() == "":
                dedented_lines.append(line[min_indent:])
            else:
                dedented_lines.append(line.lstrip())
        return "\n".join(dedented_lines)
    return text


def normalize_chunk_indentation(chunk: str) -> str:
    """Normalize tabs to spaces and adjust any mismatched indentation between a decorator and its decorated function."""
    chunk = chunk.replace("\t", "    ")
    lines = chunk.splitlines()
    
    dec_idx = -1
    dec_indent = 0
    func_idx = -1
    func_indent = 0
    
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("@"):
            dec_idx = idx
            dec_indent = len(line) - len(line.lstrip(' '))
            # Find the function line after it
            for f_idx in range(idx + 1, len(lines)):
                f_line = lines[f_idx]
                f_stripped = f_line.strip()
                if not f_stripped:
                    continue
                if f_stripped.startswith("def ") or f_stripped.startswith("async def "):
                    func_idx = f_idx
                    func_indent = len(f_line) - len(f_line.lstrip(' '))
                    break
            break
            
    if dec_idx != -1 and func_idx != -1 and func_indent != dec_indent:
        diff = func_indent - dec_indent
        new_lines = list(lines)
        for i in range(func_idx, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            leading = len(line) - len(line.lstrip(' '))
            if leading >= diff:
                new_lines[i] = line[diff:]
            else:
                new_lines[i] = line.lstrip()
        return "\n".join(new_lines)
        
    return chunk


def split_into_method_chunks(text: str) -> list[str]:
    """Normalize tabs to 4 spaces, split additions text into individual method chunks (decorated or normal)."""
    text = text.replace("\t", "    ")
    lines = text.splitlines()
    chunks = []
    current_chunk = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_chunk.append(line)
            continue
            
        is_start_line = False
        if stripped.startswith("@"):
            is_start_line = True
        elif stripped.startswith("def ") or stripped.startswith("async def "):
            # Only start a new chunk if the last non-empty line was not a decorator
            last_non_empty = None
            for l in reversed(current_chunk):
                if l.strip():
                    last_non_empty = l.strip()
                    break
            if not (last_non_empty and last_non_empty.startswith("@")):
                is_start_line = True
                
        if is_start_line and current_chunk:
            chunk_str = "\n".join(current_chunk)
            if "def " in chunk_str:
                chunks.append(chunk_str)
                current_chunk = []
                
        current_chunk.append(line)
        
    if current_chunk:
        chunk_str = "\n".join(current_chunk)
        if "def " in chunk_str:
            chunks.append(chunk_str)
            
    return chunks


def merge_additions(source: str, additions: str, imports: str) -> str:
    """Merge code additions and imports into the original source code, replacing existing methods if they overlap."""
    # Clean typographical quotes
    additions = additions.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    imports = imports.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    try:
        class_name, _ = find_primary_class(source)
        if class_name:
            import os
            os.makedirs("/home/jamie/.gemini/antigravity-ide/brain/1ddf7a38-d71b-4638-ac3b-ee3dc2974f6d/scratch", exist_ok=True)
            with open(f"/home/jamie/.gemini/antigravity-ide/brain/1ddf7a38-d71b-4638-ac3b-ee3dc2974f6d/scratch/last_additions_{class_name}.py", "w") as f:
                f.write(additions)
    except Exception:
        pass

    lines = source.splitlines()

    # 1. Insert imports at the top
    if imports.strip():
        insert_idx = 0
        try:
            tree = ast.parse(source)
            # Find the last __future__ import in the top-level body to place new imports after it
            future_lines = []
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    future_lines.append(getattr(node, "end_lineno", node.lineno))
                else:
                    break
            
            if future_lines:
                insert_idx = max(future_lines)
            elif tree.body:
                insert_idx = max(0, tree.body[0].lineno - 1)
        except Exception:
            for idx, line in enumerate(lines):
                if not line.strip().startswith("#") and line.strip():
                    insert_idx = idx
                    break
        
        import_lines = [line for line in imports.splitlines() if line.strip()]
        lines[insert_idx:insert_idx] = import_lines + [""]
        source = "\n".join(lines)

    # 2. Merge additions (replace existing methods, append new ones)
    if additions.strip():
        class_name, end_line = find_primary_class(source)
        if not class_name:
            # Fallback to appending at the end of the file if no class found
            lines = source.splitlines()
            lines.append("")
            lines.extend(additions.splitlines())
            return "\n".join(lines) + "\n"

        methods_to_replace = {}
        methods_to_append = []

        try:
            chunks = split_into_method_chunks(additions)
            for chunk in chunks:
                normalized_chunk = normalize_chunk_indentation(chunk)
                dedented_chunk = custom_dedent(normalized_chunk)
                if not dedented_chunk.strip():
                    continue
                
                # Parse single method chunk
                chunk_tree = ast.parse(dedented_chunk)
                method_node = None
                for node in chunk_tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_node = node
                        break
                        
                if not method_node:
                    continue
                    
                method_name = method_node.name
                
                # Check if this method already exists in original class
                orig_tree = ast.parse(source)
                exists = False
                for orig_node in orig_tree.body:
                    if isinstance(orig_node, ast.ClassDef) and orig_node.name == class_name:
                        for subnode in orig_node.body:
                            if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)) and subnode.name == method_name:
                                exists = True
                                break
                                
                if exists:
                    methods_to_replace[method_name] = dedented_chunk
                else:
                    methods_to_append.append(dedented_chunk)
        except Exception as e:
            # Fallback if AST parsing of additions fails: just append everything
            import sys, traceback
            print(f"[AST MERGE WARNING] Failed to parse additions: {e}", file=sys.stderr)
            traceback.print_exc()
            methods_to_append = [additions]

        # Replace existing methods in original source
        for method_name, new_method_src in methods_to_replace.items():
            replaced_source = replace_method_in_source(source, class_name, method_name, new_method_src)
            if replaced_source is not None:
                source = replaced_source

        # Append remaining new methods to the end of the class
        if methods_to_append:
            lines = source.splitlines()
            # Find end of class again after replacements
            _, end_line = find_primary_class(source)
            
            addition_lines = []
            for item in methods_to_append:
                for line in item.splitlines():
                    if line.strip():
                        addition_lines.append("    " + line)
                    else:
                        addition_lines.append("")
                addition_lines.append("")  # Blank line between appended methods
            
            if end_line is not None:
                lines.insert(end_line, "")
                for i, addition_line in enumerate(addition_lines):
                    lines.insert(end_line + 1 + i, addition_line)
            else:
                lines.append("")
                lines.extend(addition_lines)
            source = "\n".join(lines)

    return source + "\n"


class AIGenerationService:
    """Scans triad files, extracts outlines, and runs local AI code generation to merge code chunks."""

    def __init__(self, ollama_host: str | None = None) -> None:
        from app.config import load_config
        self.config = load_config()
        
        if ollama_host:
            self.ollama_host = ollama_host
        elif self.config.ai_url:
            url = self.config.ai_url.strip()
            # strip /api/generate if present
            if url.endswith("/api/generate"):
                self.ollama_host = url[:-13]
            else:
                self.ollama_host = url
        else:
            host_env = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
            if not host_env.startswith("http://") and not host_env.startswith("https://"):
                host_env = f"http://{host_env}"
            self.ollama_host = host_env
        
        if "localhost" in self.ollama_host:
            self.ollama_host = self.ollama_host.replace("localhost", "127.0.0.1")

    def get_best_model(self) -> str:
        """Query local Ollama tags and select the best coder model available."""
        if getattr(self.config, "ai_model", None):
            return self.config.ai_model
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                models = [m["name"] for m in payload.get("models", [])]

                # Priority checks
                preferred = ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "qwen2.5-coder:1.5b", "deepseek-r1:14b"]
                for p in preferred:
                    p_low = p.lower()
                    for m in models:
                        m_low = m.lower()
                        if m_low == p_low or m_low.startswith(p_low + ":"):
                            return m
                for m in models:
                    if "coder" in m.lower():
                        return m
                if models:
                    return models[0]
        except Exception:
            pass
        return "qwen2.5-coder:7b"

    def process_triad(self, model_path: str, view_path: str, controller_path: str) -> tuple[bool, str]:
        """Scan Model, View, Controller, request code additions from LLM, and merge back."""
        paths = {
            "model": model_path,
            "view": view_path,
            "controller": controller_path,
        }

        contents = {}
        class_names = {}
        outlines = {}

        for role, p in paths.items():
            if not p or not os.path.exists(p):
                return False, f"File for role '{role}' does not exist: {p}"
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                    contents[role] = content
                    class_names[role], _ = find_primary_class(content)
                    if not class_names[role]:
                        class_names[role] = Path(p).stem.title().replace("_", "")
                    outlines[role] = get_file_outline(content)
            except Exception as e:
                return False, f"Failed to read {role} file: {e}"

        request_text = None
        source_role = None
        line_idx = -1

        pattern = re.compile(r"#\s*AI-request:?\s*(.*)", re.IGNORECASE)

        for role in ["model", "view", "controller"]:
            lines = contents[role].splitlines()
            for idx, line in enumerate(lines):
                match = pattern.search(line)
                if match:
                    request_text = match.group(1).strip()
                    source_role = role
                    line_idx = idx
                    break
            if request_text:
                break

        if not request_text:
            return False, "No #AI-request tag found in Model, View, or Controller files."

        # Replace tag with timestamped AI-addition comment
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = contents[source_role].splitlines()
        orig_line = lines[line_idx]
        new_line = re.sub(r"#\s*AI-request:?\s*(.*)", f"# AI-addition ({timestamp}): \\1", orig_line, flags=re.IGNORECASE)
        lines[line_idx] = new_line
        contents[source_role] = "\n".join(lines)

        model = self.get_best_model()
        prompt = self.build_prompt(
            model_outline=outlines["model"],
            view_outline=outlines["view"],
            controller_outline=outlines["controller"],
            request_text=request_text,
            source_role=source_role,
            model_class=class_names["model"],
            view_class=class_names["view"],
            controller_class=class_names["controller"],
        )

        try:
            generated_json = self.query_ollama(model, prompt)

            # Generate stubs/boilerplates and merge
            validated_code = {}
            for role in ["model", "view", "controller"]:
                role_data = generated_json.get(f"{role}_additions", "")
                imports = generated_json.get(f"{role}_imports", "")
                if isinstance(imports, list):
                    imports = "\n".join(imports)
                else:
                    imports = str(imports or "").strip()
                
                if isinstance(role_data, dict):
                    # New structured schema
                    methods_list = role_data.get("methods", [])
                    signals_list = role_data.get("signals", [])
                    imports_list = role_data.get("imports", [])
                    
                    method_strings = []
                    for m in methods_list:
                        if isinstance(m, dict):
                            method_strings.append(generate_method_code(m))
                            
                    additions = "\n\n".join(method_strings)
                    if imports_list:
                        imports = "\n".join(imports_list)
                    
                    source_code = contents[role]
                    if role == "view" and signals_list:
                        source_code = insert_signals_in_class(source_code, class_names[role], signals_list)
                else:
                    # Old schema: raw string additions
                    additions = str(role_data or "").strip()
                    source_code = contents[role]
                
                # Merge additions and imports
                merged = merge_additions(source_code, additions, imports)
                
                # Compile to check syntax
                ast.parse(merged)
                validated_code[role] = merged

            # Write files
            for role, code in validated_code.items():
                with open(paths[role], "w", encoding="utf-8") as f:
                    f.write(code)

            return True, f"Boilerplate stubs completed successfully using model {model}."
        except Exception as e:
            return False, f"AI boilerplate generation failed: {e}"

    def build_prompt(
        self,
        model_outline: str,
        view_outline: str,
        controller_outline: str,
        request_text: str,
        source_role: str,
        model_class: str,
        view_class: str,
        controller_class: str,
    ) -> str:
        """Format the system and user instructions for the Ollama model to generate structured boilerplate metadata."""
        return f"""You are a helpful software engineering assistant.
We have a Model-View-Controller (MVC) triad of Python files:
1. Model file: containing class `{model_class}`
2. View file: containing class `{view_class}`
3. Controller file: containing class `{controller_class}`

Here is the current outline (structure, imports, constructors, and layouts) of each file:

--- MODEL OUTLINE ---
{model_outline}

--- VIEW OUTLINE ---
{view_outline}

--- CONTROLLER OUTLINE ---
{controller_outline}

The user has requested the following feature to be implemented across this MVC triad:
"{request_text}"

Your task is to analyze the outlines and request, and return a JSON object listing the required boilerplate methods, class-level PyQt signals, and imports to be added or modified in each file.
You must ONLY output the JSON object. Do NOT write any code implementation or business logic. All method stubs will be generated programmatically by the system.

You MUST return a JSON object with the following schema:
{{
  "model_additions": {{
    "methods": [
      {{
        "name": "method_name",
        "args": "arguments (e.g. 'self' or 'self, data')",
        "decorator": "decorator if any (e.g. 'property' or 'classmethod'), or empty string",
        "docstring": "short description of the method's purpose"
      }}
    ],
    "imports": [
      "import statements to add (e.g. 'from typing import List')"
    ]
  }},
  "view_additions": {{
    "methods": [
      {{
        "name": "method_name",
        "args": "arguments (e.g. 'self')",
        "decorator": "decorator if any, or empty string",
        "docstring": "short description of the method's purpose"
      }}
    ],
    "signals": [
      "signal declaration lines to add (e.g. 'clear_history_requested = pyqtSignal()')"
    ],
    "imports": [
      "import statements to add"
    ]
  }},
  "controller_additions": {{
    "methods": [
      {{
        "name": "method_name",
        "args": "arguments",
        "decorator": "",
        "docstring": "description"
      }}
    ],
    "imports": [
      "import statements to add"
    ]
  }}
}}

Ensure all method names and signal names are clean and match Python conventions.
Ensure that the JSON is perfectly valid and is the ONLY thing you print.
Do NOT wrap the JSON in Markdown backticks or write any other text.
"""

    def query_ollama(self, model: str, prompt: str) -> dict:
        """Call Ollama generation endpoint with JSON output mode."""
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                res_payload = json.loads(response.read().decode("utf-8"))
                response_text = res_payload.get("response", "").strip()

                # Clean reasoning thoughts
                if "<thought>" in response_text:
                    response_text = re.sub(r"<thought>.*?</thought>", "", response_text, flags=re.DOTALL).strip()

                first_brace = response_text.find("{")
                last_brace = response_text.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    response_text = response_text[first_brace:last_brace+1]

                if response_text.startswith("```"):
                    lines = response_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    response_text = "\n".join(lines).strip()

                return json.loads(response_text)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Could not connect to Ollama at {url}: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama returned invalid JSON: {e}. Raw response: {response_text[:300]}")
