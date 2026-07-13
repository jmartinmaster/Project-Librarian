# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Copyright (c) GNU General Public License v3.0
#
# You should have received a copy of the GNU General Public License
# along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.

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


def merge_additions(source: str, additions: str, imports: str) -> str:
    """Merge code additions and imports into the original source code."""
    lines = source.splitlines()

    # 1. Insert imports at the top
    if imports.strip():
        insert_idx = 0
        try:
            tree = ast.parse(source)
            if tree.body:
                insert_idx = max(0, tree.body[0].lineno - 1)
        except Exception:
            for idx, line in enumerate(lines):
                if not line.strip().startswith("#") and line.strip():
                    insert_idx = idx
                    break
        
        import_lines = [line for line in imports.splitlines() if line.strip()]
        lines[insert_idx:insert_idx] = import_lines + [""]

    # 2. Append additions to the primary class
    if additions.strip():
        temp_source = "\n".join(lines)
        class_name, end_line = find_primary_class(temp_source)
        
        addition_lines = []
        for line in additions.splitlines():
            if line.strip():
                if line.startswith("    ") or line.startswith("\t"):
                    addition_lines.append(line)
                else:
                    addition_lines.append("    " + line)
            else:
                addition_lines.append("")

        if end_line is not None:
            lines.insert(end_line, "")
            for i, addition_line in enumerate(addition_lines):
                lines.insert(end_line + 1 + i, addition_line)
        else:
            lines.append("")
            lines.extend(addition_lines)

    return "\n".join(lines) + "\n"


class AIGenerationService:
    """Scans triad files, extracts outlines, and runs local AI code generation to merge code chunks."""

    def __init__(self, ollama_host: str | None = None) -> None:
        if not ollama_host:
            host_env = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
            if not host_env.startswith("http://") and not host_env.startswith("https://"):
                host_env = f"http://{host_env}"
            self.ollama_host = host_env
        else:
            self.ollama_host = ollama_host
        
        if "localhost" in self.ollama_host:
            self.ollama_host = self.ollama_host.replace("localhost", "127.0.0.1")

    def get_best_model(self) -> str:
        """Query local Ollama tags and select the best coder model available."""
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

            # Validate generated additions syntax
            validated_code = {}
            for role in ["model", "view", "controller"]:
                additions = generated_json.get(f"{role}_additions", "").strip()
                imports = generated_json.get(f"{role}_imports", "").strip()
                
                # Check syntax of additions
                if additions:
                    try:
                        dummy_code = merge_additions('class Dummy:\n    pass', additions, '')
                        ast.parse(dummy_code)
                    except SyntaxError as se:
                        return False, f"AI generated invalid syntax for {role} additions: {se}"

                merged = merge_additions(contents[role], additions, imports)
                validated_code[role] = merged

            # Write files
            for role, code in validated_code.items():
                with open(paths[role], "w", encoding="utf-8") as f:
                    f.write(code)

            return True, f"AI generation completed successfully using model {model}."
        except Exception as e:
            return False, f"AI generation failed: {e}"

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
        """Format the system and user instructions for the Ollama model."""
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

There is an AI request: "{request_text}" originating from the '{source_role}' file.

Your task is to generate the boilerplate methods and imports to propagate this feature across the triad.

STRICT ARCHITECTURE CONSTRAINTS:
1. View (`{view_class}`):
   - ONLY handles GUI widgets, layout, and display/rendering.
   - Must NOT contain or access references to the Model or Controller (do not use `self.model` or `self.controller`).
   - Declares custom Qt signals to notify actions (e.g. `save_requested = pyqtSignal()`).
   - Exposes values only via getters/setters (e.g. `get_value_a()`, `update_display(val)`).
2. Model (`{model_class}`):
   - ONLY handles data, computations, and business logic.
   - Must NOT reference the View or Controller.
   - Exposes methods to perform calculations or save state (e.g. `save_result_to_file(filename, result)`).
3. Controller (`{controller_class}`):
   - Acts as the wiring. It has references to both `self.model` and `self.view`.
   - Wires the View's signals to its own slot methods inside `__init__`.
   - In its slots, it gets data from the View, updates the Model, and triggers View changes.

IMPORTANT: Read the constructor (`__init__`) and layout (`init_ui`) method bodies in the outlines to find the exact names of existing widgets (e.g., `self.display_label`) and signals. You MUST use these exact names in your generated code. If you use external widgets like QFileDialog, ensure you include them in the respective `_imports` key.

Return ONLY the code changes (imports and methods) to be appended/inserted. Do not return the complete original files.
Your output MUST be a single JSON object with exactly these six keys:
- 'model_imports': new import lines to add to the model file (or empty string if none)
- 'model_additions': new method definitions to append to the class `{model_class}` (or empty string if none)
- 'view_imports': new import lines to add to the view file (or empty string if none)
- 'view_additions': new method definitions to append to the class `{view_class}` (or empty string if none)
- 'controller_imports': new import lines to add to the controller file (or empty string if none)
- 'controller_additions': new method definitions to append to the class `{controller_class}` (or empty string if none)

The values must be raw Python strings. Indent any method additions properly (typically 4 spaces).

Example output format:
{{
  "model_imports": "import json",
  "model_additions": "    def new_method(self):\n        pass",
  "view_imports": "",
  "view_additions": "    def setup_ui(self):\n        pass",
  "controller_imports": "",
  "controller_additions": "    def on_click(self):\n        pass"
}}
Do not include any extra text, explanations, or markdown code blocks (like ```json) outside the JSON. Return only the JSON object.
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
