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

"""AI-driven code generation service for propagating boilerplate methods across MVC triads."""

from __future__ import annotations

import datetime
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


class AIGenerationService:
    """Scans triad files for #AI-request tags and runs local AI code generation."""

    def __init__(self, ollama_host: str | None = None) -> None:
        if not ollama_host:
            host_env = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
            if not host_env.startswith("http://") and not host_env.startswith("https://"):
                host_env = f"http://{host_env}"
            self.ollama_host = host_env
        else:
            self.ollama_host = ollama_host

    def get_best_model(self) -> str:
        """Query local Ollama tags and select the best coder model available."""
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                models = [m["name"] for m in payload.get("models", [])]

                # Priority checks (case-insensitive)
                preferred = ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "qwen2.5-coder:1.5b", "deepseek-r1:14b"]
                for p in preferred:
                    p_low = p.lower()
                    for m in models:
                        m_low = m.lower()
                        if m_low == p_low or m_low.startswith(p_low + ":"):
                            return m
                # Fallback to any containing coder
                for m in models:
                    if "coder" in m.lower():
                        return m
                # Fallback to first available
                if models:
                    return models[0]
        except Exception:
            pass
        return "qwen2.5-coder:7b"

    def process_triad(self, model_path: str, view_path: str, controller_path: str) -> tuple[bool, str]:
        """Scan Model, View, and Controller files, execute propagation, and replace tag."""
        paths = {
            "model": model_path,
            "view": view_path,
            "controller": controller_path,
        }

        contents = {}
        for role, p in paths.items():
            if not p or not os.path.exists(p):
                return False, f"File for role '{role}' does not exist: {p}"
            try:
                with open(p, "r", encoding="utf-8") as f:
                    contents[role] = f.read()
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
            model_content=contents["model"],
            view_content=contents["view"],
            controller_content=contents["controller"],
            request_text=request_text,
            source_role=source_role,
            model_path=model_path,
            view_path=view_path,
            controller_path=controller_path,
        )

        try:
            generated_json = self.query_ollama(model, prompt)

            # Validate all generated files before writing any of them to disk
            validated_code = {}
            import ast
            for role, key in [("model", "model_code"), ("view", "view_code"), ("controller", "controller_code")]:
                code = generated_json.get(key, "").strip()
                if not code:
                    validated_code[role] = contents[role]
                    continue

                # 1. Syntax check for Python
                if paths[role].endswith(".py"):
                    try:
                        ast.parse(code)
                    except SyntaxError as se:
                        return False, f"AI generated invalid Python syntax for {role}: {se}"

                # 2. Stub/size checking: if original was long and generated is extremely short
                orig_len = len(contents[role])
                gen_len = len(code)
                if orig_len > 1500 and gen_len < 300:
                    return False, f"AI generation returned a short stub for {role} (length {gen_len}) instead of full file content."

                validated_code[role] = code

            # Write only after all files pass validation
            for role, code in validated_code.items():
                with open(paths[role], "w", encoding="utf-8") as f:
                    f.write(code)

            return True, f"AI generation completed successfully using model {model}."
        except Exception as e:
            return False, f"AI generation failed: {e}"

    def build_prompt(
        self,
        model_content: str,
        view_content: str,
        controller_content: str,
        request_text: str,
        source_role: str,
        model_path: str,
        view_path: str,
        controller_path: str,
    ) -> str:
        """Format the system and user instructions for the Ollama model."""
        return f"""You are a helpful software engineering assistant.
We have a Model-View-Controller (MVC) triad of Python files:
1. Model file: {model_path}
2. View file: {view_path}
3. Controller file: {controller_path}

Here is the current content of each file:

--- MODEL ({model_path}) ---
{model_content}

--- VIEW ({view_path}) ---
{view_content}

--- CONTROLLER ({controller_path}) ---
{controller_content}

There is an AI request: "{request_text}" originating from the '{source_role}' file.

Your task is to generate the boilerplate methods and updates for ALL THREE files so that the new feature is properly implemented and propagates across the triad.
- The Model should have the data/business logic methods.
- The View should have the UI widgets and display methods.
- The Controller should connect the View's UI signals to the Model's logic.

Ensure you integrate the new methods smoothly into the existing classes and code structure. Do not change or remove unrelated existing logic.
Return the updated code for ALL THREE files in a single JSON object. The output MUST be valid JSON with exactly three keys: 'model_code', 'view_code', and 'controller_code'. The values must be the complete updated file contents as strings.
IMPORTANT: You must return the COMPLETE updated file contents for each file, including all existing classes, methods, and imports. Do not return stubs, placeholders, or partial code.

Example output format:
{{
  "model_code": "...complete updated model file content...",
  "view_code": "...complete updated view file content...",
  "controller_code": "...complete updated controller file content..."
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
            with urllib.request.urlopen(req, timeout=120) as response:
                res_payload = json.loads(response.read().decode("utf-8"))
                response_text = res_payload.get("response", "").strip()

                # Clean reasoning thoughts
                if "<thought>" in response_text:
                    response_text = re.sub(r"<thought>.*?</thought>", "", response_text, flags=re.DOTALL).strip()

                # Find first { and last } to extract JSON body
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
