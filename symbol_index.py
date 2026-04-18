import argparse
import ast
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("build") / "symbol-index"
JSON_OUTPUT_NAME = "symbol-index.json"
MARKDOWN_OUTPUT_NAME = "symbol-index.md"
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "data",
    "dist",
    "env",
    "exports",
    "logs",
    "venv",
}
MISSING = object()


class SymbolIndexError(RuntimeError):
    pass


def _repo_root_from_here():
    return Path(__file__).resolve().parent


def _safe_unparse(node):
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _literal_value(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _attribute_path_text(node):
    parts = []
    current_node = node
    while isinstance(current_node, ast.Attribute):
        parts.append(current_node.attr)
        current_node = current_node.value
    if isinstance(current_node, ast.Name):
        parts.append(current_node.id)
        return ".".join(reversed(parts))
    return None


def _value_preview(node, max_length=120):
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        compact_text = repr(node.value)
    elif isinstance(node, ast.Name):
        compact_text = node.id
    elif isinstance(node, ast.Attribute):
        compact_text = _attribute_path_text(node) or "attribute"
    elif isinstance(node, ast.Call):
        function_name = _safe_unparse(node.func) or "call"
        compact_text = f"{function_name}(...)"
    elif isinstance(node, ast.Dict):
        compact_text = f"dict[{len(node.keys)}]"
    elif isinstance(node, ast.List):
        compact_text = f"list[{len(node.elts)}]"
    elif isinstance(node, ast.Tuple):
        compact_text = f"tuple[{len(node.elts)}]"
    elif isinstance(node, ast.Set):
        compact_text = f"set[{len(node.elts)}]"
    else:
        compact_text = node.__class__.__name__

    if len(compact_text) <= max_length:
        return compact_text
    return f"{compact_text[: max_length - 3]}..."


def _doc_summary(node):
    doc_text = ast.get_docstring(node)
    if not doc_text:
        return None
    summary_line = doc_text.strip().splitlines()[0].strip()
    return summary_line or None


def _annotation_text(node):
    return _safe_unparse(node.annotation) if getattr(node, "annotation", None) is not None else None


def _decorator_texts(node):
    return [text for text in (_safe_unparse(entry) for entry in node.decorator_list) if text]


def _base_texts(node):
    return [text for text in (_safe_unparse(entry) for entry in node.bases) if text]


def _is_dataclass(node):
    for decorator in node.decorator_list:
        decorator_text = (_safe_unparse(decorator) or "").split("(", 1)[0]
        if decorator_text.split(".")[-1] == "dataclass":
            return True
    return False


def _classification_for_module_variable(name):
    if name in {"__module_name__", "__version__"}:
        return "module_metadata"
    if name.isupper():
        return "module_constant"
    return "module_variable"


def _classification_for_class_attribute(name, dataclass_enabled):
    if dataclass_enabled:
        return "dataclass_field"
    if name.isupper():
        return "class_constant"
    return "class_attribute"


def _extract_name_targets(target):
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.List, ast.Tuple)):
        matches = []
        for child in target.elts:
            matches.extend(_extract_name_targets(child))
        return matches
    return []


def _format_argument(arg_node, default_value=MISSING, prefix=""):
    text = f"{prefix}{arg_node.arg}"
    annotation_text = _safe_unparse(arg_node.annotation)
    if annotation_text:
        text += f": {annotation_text}"
    if default_value is not MISSING:
        text += f" = {_value_preview(default_value, max_length=60)}"
    return text


def _function_signature(node):
    args_text = []
    positional_args = list(node.args.posonlyargs) + list(node.args.args)
    positional_defaults = [MISSING] * (len(positional_args) - len(node.args.defaults)) + list(node.args.defaults)

    for index, arg_node in enumerate(node.args.posonlyargs):
        default_value = positional_defaults[index]
        if default_value is MISSING:
            args_text.append(_format_argument(arg_node))
        else:
            args_text.append(_format_argument(arg_node, default_value=default_value))

    if node.args.posonlyargs:
        args_text.append("/")

    start_index = len(node.args.posonlyargs)
    for offset, arg_node in enumerate(node.args.args, start=start_index):
        default_value = positional_defaults[offset]
        if default_value is MISSING:
            args_text.append(_format_argument(arg_node))
        else:
            args_text.append(_format_argument(arg_node, default_value=default_value))

    if node.args.vararg is not None:
        args_text.append(_format_argument(node.args.vararg, prefix="*"))
    elif node.args.kwonlyargs:
        args_text.append("*")

    for arg_node, default_value in zip(node.args.kwonlyargs, node.args.kw_defaults):
        if default_value is None:
            args_text.append(_format_argument(arg_node))
        else:
            args_text.append(_format_argument(arg_node, default_value=default_value))

    if node.args.kwarg is not None:
        args_text.append(_format_argument(node.args.kwarg, prefix="**"))

    return_annotation = _safe_unparse(node.returns)
    return_suffix = f" -> {return_annotation}" if return_annotation else ""
    function_prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{function_prefix} {node.name}({', '.join(args_text)}){return_suffix}"


def _build_function_entry(node, kind):
    return {
        "name": node.name,
        "line": node.lineno,
        "kind": kind,
        "signature": _function_signature(node),
        "decorators": _decorator_texts(node),
        "doc_summary": _doc_summary(node),
        "async": isinstance(node, ast.AsyncFunctionDef),
    }


class _SelfAttributeCollector(ast.NodeVisitor):
    def __init__(self, method_name, sink):
        self.method_name = method_name
        self.sink = sink

    def visit_FunctionDef(self, node):
        return None

    def visit_AsyncFunctionDef(self, node):
        return None

    def visit_ClassDef(self, node):
        return None

    def visit_Lambda(self, node):
        return None

    def visit_Assign(self, node):
        for target in node.targets:
            self._record_target(target, node)
        self.generic_visit(node.value)

    def visit_AnnAssign(self, node):
        self._record_target(node.target, node)
        if node.value is not None:
            self.generic_visit(node.value)

    def visit_AugAssign(self, node):
        self._record_target(node.target, node)
        self.generic_visit(node.value)

    def _record_target(self, target, node):
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
            entry = self.sink.setdefault(
                target.attr,
                {
                    "name": target.attr,
                    "kind": "instance_attribute",
                    "line": node.lineno,
                    "annotation": None,
                    "value_preview": None,
                    "assigned_in": [],
                },
            )
            entry["line"] = min(entry["line"], node.lineno)
            if isinstance(node, ast.AnnAssign):
                entry["annotation"] = _safe_unparse(node.annotation)
            if entry["value_preview"] is None:
                entry["value_preview"] = _value_preview(getattr(node, "value", None))
            if self.method_name not in entry["assigned_in"]:
                entry["assigned_in"].append(self.method_name)
            return

        if isinstance(target, (ast.List, ast.Tuple)):
            for child in target.elts:
                self._record_target(child, node)


def _collect_assignment_entries(node, classification_fn):
    if isinstance(node, ast.Assign):
        entries = []
        for target in node.targets:
            for name_node in _extract_name_targets(target):
                entries.append(
                    {
                        "name": name_node.id,
                        "line": node.lineno,
                        "kind": classification_fn(name_node.id),
                        "annotation": None,
                        "value_preview": _value_preview(node.value),
                    }
                )
        return entries

    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [
            {
                "name": node.target.id,
                "line": node.lineno,
                "kind": classification_fn(node.target.id),
                "annotation": _annotation_text(node),
                "value_preview": _value_preview(node.value),
            }
        ]

    return []


def _merge_attribute_entries(class_entries, instance_entries):
    merged_entries = {entry["name"]: dict(entry) for entry in class_entries}
    for name, instance_entry in instance_entries.items():
        if name not in merged_entries:
            merged_entries[name] = dict(instance_entry)
            continue

        current_entry = merged_entries[name]
        current_entry["line"] = min(current_entry["line"], instance_entry["line"])
        assigned_in = current_entry.setdefault("assigned_in", [])
        for method_name in instance_entry.get("assigned_in", []):
            if method_name not in assigned_in:
                assigned_in.append(method_name)
        if current_entry.get("value_preview") is None:
            current_entry["value_preview"] = instance_entry.get("value_preview")
        if current_entry.get("annotation") is None:
            current_entry["annotation"] = instance_entry.get("annotation")
        if current_entry.get("kind") == "class_attribute":
            current_entry["kind"] = "instance_attribute"

    ordered_entries = sorted(merged_entries.values(), key=lambda entry: (entry["line"], entry["name"]))
    for entry in ordered_entries:
        if "assigned_in" in entry:
            entry["assigned_in"] = sorted(entry["assigned_in"])
    return ordered_entries


def _build_class_entry(node):
    dataclass_enabled = _is_dataclass(node)
    class_attributes = []
    methods = []
    instance_attributes = {}

    for child in node.body:
        if isinstance(child, (ast.Assign, ast.AnnAssign)):
            class_attributes.extend(
                _collect_assignment_entries(
                    child,
                    lambda name, dataclass_enabled=dataclass_enabled: _classification_for_class_attribute(name, dataclass_enabled),
                )
            )
            continue

        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_build_function_entry(child, kind="method"))
            collector = _SelfAttributeCollector(child.name, instance_attributes)
            for statement in child.body:
                collector.visit(statement)

    return {
        "name": node.name,
        "line": node.lineno,
        "kind": "class",
        "bases": _base_texts(node),
        "decorators": _decorator_texts(node),
        "doc_summary": _doc_summary(node),
        "dataclass": dataclass_enabled,
        "attributes": _merge_attribute_entries(class_attributes, instance_attributes),
        "methods": methods,
    }


def _relative_path_text(path, repo_root):
    return path.relative_to(repo_root).as_posix()


def _file_area(relative_path):
    if relative_path.startswith("app/controllers/"):
        return "controllers"
    if relative_path.startswith("app/models/"):
        return "models"
    if relative_path.startswith("app/views/"):
        return "views"
    if relative_path.startswith("app/"):
        return "app"
    return "root"


def _load_managed_module_names(repo_root):
    registry_path = repo_root / "app" / "module_registry.json"
    if not registry_path.exists():
        return []

    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SymbolIndexError(f"Unable to read managed module registry from {registry_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SymbolIndexError(f"Unable to parse managed module registry from {registry_path}: {exc}") from exc

    modules = payload.get("modules", []) if isinstance(payload, dict) else []
    if not isinstance(modules, list):
        raise SymbolIndexError(f"Managed module registry at {registry_path} must define a 'modules' list.")

    managed_module_names = []
    for module_entry in modules:
        if not isinstance(module_entry, dict):
            continue
        module_name = str(module_entry.get("name") or "").strip()
        if module_name:
            managed_module_names.append(module_name)
    return managed_module_names


def _iter_python_files(repo_root):
    files = []
    for root_path, dir_names, file_names in os.walk(repo_root, topdown=True):
        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if dir_name not in EXCLUDED_DIRECTORY_NAMES and not dir_name.startswith(".venv")
        ]
        for file_name in file_names:
            if not file_name.endswith(".py"):
                continue
            files.append(Path(root_path) / file_name)
    return sorted(files, key=lambda path: _relative_path_text(path, repo_root))


def _build_file_entry(path, repo_root, managed_module_names):
    try:
        source_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SymbolIndexError(f"Unable to read {path}: {exc}") from exc

    try:
        tree = ast.parse(source_text, filename=str(path))
    except SyntaxError as exc:
        raise SymbolIndexError(f"Unable to parse {path}: {exc}") from exc

    relative_path = _relative_path_text(path, repo_root)
    entry = {
        "path": relative_path,
        "area": _file_area(relative_path),
        "doc_summary": _doc_summary(tree),
        "managed_module": path.parent == (repo_root / "app") and path.stem in managed_module_names,
        "module_name": None,
        "version": None,
        "variables": [],
        "functions": [],
        "classes": [],
    }

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            variable_entries = _collect_assignment_entries(node, _classification_for_module_variable)
            entry["variables"].extend(variable_entries)
            for variable_entry in variable_entries:
                if variable_entry["name"] == "__module_name__":
                    entry["module_name"] = _literal_value(getattr(node, "value", None))
                elif variable_entry["name"] == "__version__":
                    entry["version"] = _literal_value(getattr(node, "value", None))
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entry["functions"].append(_build_function_entry(node, kind="function"))
            continue

        if isinstance(node, ast.ClassDef):
            entry["classes"].append(_build_class_entry(node))

    entry["variables"].sort(key=lambda variable: (variable["line"], variable["name"]))
    entry["functions"].sort(key=lambda function: (function["line"], function["name"]))
    entry["classes"].sort(key=lambda cls: (cls["line"], cls["name"]))
    return entry


def _build_summary(file_entries, managed_module_names):
    counts = Counter()
    area_counts = Counter()

    for file_entry in file_entries:
        counts["files"] += 1
        counts["module_variables"] += len(file_entry["variables"])
        counts["functions"] += len(file_entry["functions"])
        counts["classes"] += len(file_entry["classes"])
        if file_entry["managed_module"]:
            counts["managed_module_entries"] += 1
        area_counts[file_entry["area"]] += 1

        for class_entry in file_entry["classes"]:
            counts["methods"] += len(class_entry["methods"])
            counts["attributes"] += len(class_entry["attributes"])
            counts["dataclass_fields"] += sum(1 for attribute in class_entry["attributes"] if attribute["kind"] == "dataclass_field")
            counts["instance_attributes"] += sum(1 for attribute in class_entry["attributes"] if attribute["kind"] == "instance_attribute")

    return {
        "files": counts["files"],
        "classes": counts["classes"],
        "methods": counts["methods"],
        "functions": counts["functions"],
        "module_variables": counts["module_variables"],
        "attributes": counts["attributes"],
        "dataclass_fields": counts["dataclass_fields"],
        "instance_attributes": counts["instance_attributes"],
        "managed_module_entries": counts["managed_module_entries"],
        "managed_module_names": managed_module_names,
        "areas": dict(sorted(area_counts.items())),
    }


def _render_metadata_line(label, value):
    if value in (None, "", []):
        return None
    if isinstance(value, list):
        value = ", ".join(value)
    return f"- {label}: {value}"


def _markdown_path(output_dir, repo_root, relative_path, line=None):
    file_path = Path(repo_root) / relative_path
    link_target = Path(os.path.relpath(file_path, output_dir)).as_posix()
    if line is not None:
        link_target = f"{link_target}#L{line}"
    return link_target


def _render_variable_lines(entries, indent=""):
    if not entries:
        return [f"{indent}- None"]

    lines = []
    for entry in entries:
        detail_parts = [entry["kind"]]
        if entry.get("annotation"):
            detail_parts.append(f"annotation: {entry['annotation']}")
        if entry.get("assigned_in"):
            detail_parts.append(f"assigned in: {', '.join(entry['assigned_in'])}")
        if entry.get("value_preview"):
            detail_parts.append(f"value: {entry['value_preview']}")
        details_text = "; ".join(detail_parts)
        lines.append(
            f"{indent}- `{entry['name']}` at line {entry['line']} ({details_text})"
        )
    return lines


def render_markdown(payload, output_dir):
    repo_root = Path(payload["repo_root"])
    lines = [
        "# Python Symbol Index",
        "",
        "Generated from static AST analysis for fast symbol lookup.",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Files indexed: {payload['summary']['files']}",
        f"- Classes: {payload['summary']['classes']}",
        f"- Methods: {payload['summary']['methods']}",
        f"- Functions: {payload['summary']['functions']}",
        f"- Module variables: {payload['summary']['module_variables']}",
        f"- Class and instance attributes: {payload['summary']['attributes']}",
        f"- Dataclass fields: {payload['summary']['dataclass_fields']}",
        f"- Instance attributes: {payload['summary']['instance_attributes']}",
        f"- Managed module entry files: {payload['summary']['managed_module_entries']}",
        "- Variable scope: module-level assignments, dataclass fields, class attributes, and self-assigned instance attributes.",
        "- Excluded: local variables inside functions and methods.",
        "",
        "## Quick Jump",
        "",
    ]

    grouped_files = defaultdict(list)
    for file_entry in payload["files"]:
        grouped_files[file_entry["area"]].append(file_entry)

    for area_name in sorted(grouped_files):
        lines.append(f"### {area_name.title()}")
        for file_entry in grouped_files[area_name]:
            summary_bits = [
                f"{len(file_entry['classes'])} classes",
                f"{len(file_entry['functions'])} functions",
                f"{len(file_entry['variables'])} module vars",
            ]
            lines.append(
                f"- [{file_entry['path']}]({_markdown_path(output_dir, repo_root, file_entry['path'])})"
                f" ({', '.join(summary_bits)})"
            )
        lines.append("")

    for area_name in sorted(grouped_files):
        lines.append(f"## {area_name.title()}")
        lines.append("")
        for file_entry in grouped_files[area_name]:
            lines.append(f"### [{file_entry['path']}]({_markdown_path(output_dir, repo_root, file_entry['path'])})")
            metadata_lines = [
                _render_metadata_line("Module Label", file_entry.get("module_name")),
                _render_metadata_line("Version", file_entry.get("version")),
                _render_metadata_line("Managed Module Entry", "yes" if file_entry.get("managed_module") else None),
                _render_metadata_line("Summary", file_entry.get("doc_summary")),
            ]
            lines.extend(line for line in metadata_lines if line)

            lines.append("")
            lines.append("#### Module Variables")
            lines.extend(_render_variable_lines(file_entry["variables"]))
            lines.append("")

            lines.append("#### Functions")
            if file_entry["functions"]:
                for function_entry in file_entry["functions"]:
                    function_line = (
                        f"- `{function_entry['signature']}` at line {function_entry['line']}"
                    )
                    if function_entry.get("decorators"):
                        function_line += f" (decorators: {', '.join(function_entry['decorators'])})"
                    if function_entry.get("doc_summary"):
                        function_line += f" - {function_entry['doc_summary']}"
                    lines.append(function_line)
            else:
                lines.append("- None")
            lines.append("")

            lines.append("#### Classes")
            if file_entry["classes"]:
                for class_entry in file_entry["classes"]:
                    class_link = _markdown_path(output_dir, repo_root, file_entry["path"], line=class_entry["line"])
                    class_line = f"- [{class_entry['name']}]({class_link}) at line {class_entry['line']}"
                    if class_entry.get("bases"):
                        class_line += f" (bases: {', '.join(class_entry['bases'])})"
                    if class_entry.get("decorators"):
                        class_line += f" (decorators: {', '.join(class_entry['decorators'])})"
                    if class_entry.get("doc_summary"):
                        class_line += f" - {class_entry['doc_summary']}"
                    lines.append(class_line)

                    lines.append("  - Attributes")
                    lines.extend(_render_variable_lines(class_entry["attributes"], indent="    "))
                    lines.append("  - Methods")
                    if class_entry["methods"]:
                        for method_entry in class_entry["methods"]:
                            method_line = f"    - `{method_entry['signature']}` at line {method_entry['line']}"
                            if method_entry.get("decorators"):
                                method_line += f" (decorators: {', '.join(method_entry['decorators'])})"
                            if method_entry.get("doc_summary"):
                                method_line += f" - {method_entry['doc_summary']}"
                            lines.append(method_line)
                    else:
                        lines.append("    - None")
            else:
                lines.append("- None")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_symbol_index(repo_root=None, output_dir=None):
    repo_root = Path(repo_root or _repo_root_from_here()).resolve()
    output_dir = Path(output_dir or (repo_root / DEFAULT_OUTPUT_DIR)).resolve()
    managed_module_names = _load_managed_module_names(repo_root)
    file_entries = [_build_file_entry(path, repo_root, managed_module_names) for path in _iter_python_files(repo_root)]
    summary = _build_summary(file_entries, managed_module_names)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "summary": summary,
        "files": file_entries,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_OUTPUT_NAME
    markdown_path = output_dir / MARKDOWN_OUTPUT_NAME
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload, output_dir), encoding="utf-8")

    return {
        "summary": summary,
        "json_path": json_path,
        "markdown_path": markdown_path,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a static symbol index for the Python source tree.")
    parser.add_argument(
        "--repo-root",
        default=str(_repo_root_from_here()),
        help="Repository root to index. Defaults to the current repository.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory that receives symbol-index.json and symbol-index.md.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (repo_root / output_dir).resolve()

    result = generate_symbol_index(repo_root=repo_root, output_dir=output_dir)
    summary = result["summary"]
    print(
        "Generated symbol index: "
        f"{summary['files']} files, "
        f"{summary['classes']} classes, "
        f"{summary['methods']} methods, "
        f"{summary['functions']} functions"
    )
    print(f"JSON: {result['json_path']}")
    print(f"Markdown: {result['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())