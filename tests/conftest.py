"""Shared fixtures for Project Librarian smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import AppConfig


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a small sample repository tree for indexing tests."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    (app_dir / "sample.py").write_text(
        """
class Example:
    def ping(self, value):
        return value

def add(a, b):
    return a + b
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (tmp_path / "sample.c").write_text(
        """
struct person { int id; };
int sum(int a, int b) { return a + b; }
""".strip()
        + "\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def app_config(sample_repo: Path) -> AppConfig:
    """Return a baseline config targeting the sample repo."""
    return AppConfig(
        project_root=str(sample_repo),
        output_dir="build",
        excluded_dirs=[".git", ".venv", "__pycache__", "build"],
        file_extensions=[".py", ".c", ".h", ".md", ".json", ".txt"],
        refresh_interval_seconds=30,
        index_python=True,
        index_c=True,
        excel_folder="",
        excel_keyword_columns=[],
    )
