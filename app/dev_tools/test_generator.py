"""Generate smoke test drafts using a local Ollama REST endpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import requests

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:14b"


def infer_smoke_target(module_path: Path, project_root: Path) -> Path:
    """Infer the destination smoke-test path for a given module path."""
    relative = module_path.relative_to(project_root)
    if relative.parts[:2] == ("app", "indexer"):
        subfolder = "indexers"
    elif relative.parts[:2] == ("app", "search"):
        subfolder = "search"
    elif relative.parts[:2] == ("app", "ui"):
        subfolder = "ui"
    else:
        subfolder = "integration"

    return project_root / "tests" / "smoke" / subfolder / f"test_{module_path.stem}.py"


def build_prompt(module_path: Path, module_source: str) -> str:
    """Build a structured prompt requesting pytest smoke tests."""
    return (
        "Create concise pytest smoke tests for this Python module.\n"
        "Rules:\n"
        "- Return Python test code only.\n"
        "- Use deterministic assertions.\n"
        "- Avoid placeholders and TODO comments.\n"
        "- Focus on construction, basic behavior, and error boundaries.\n"
        f"Module path: {module_path.as_posix()}\n"
        "Module source follows:\n"
        "```python\n"
        f"{module_source}\n"
        "```\n"
    )


def generate_test_text(module_path: Path, model: str, ollama_url: str) -> str:
    """Call Ollama and return generated test code text."""
    source_text = module_path.read_text(encoding="utf-8")
    prompt = build_prompt(module_path, source_text)
    response = requests.post(
        ollama_url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    result = str(payload.get("response", "")).strip()
    if not result:
        raise RuntimeError("Ollama returned an empty response.")
    return result + "\n"


def main() -> int:
    """Command-line entrypoint for smoke-test generation."""
    parser = argparse.ArgumentParser(description="Generate smoke tests with local Ollama.")
    parser.add_argument("module", help="Path to source module, e.g. app/indexer/python_indexer.py")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--url", default=DEFAULT_OLLAMA_URL, help="Ollama generate endpoint URL")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    module_path = (project_root / args.module).resolve()
    if not module_path.exists():
        raise FileNotFoundError(f"Source module does not exist: {module_path}")

    test_path = infer_smoke_target(module_path, project_root)
    generated = generate_test_text(module_path=module_path, model=args.model, ollama_url=args.url)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(generated, encoding="utf-8")
    print(test_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
