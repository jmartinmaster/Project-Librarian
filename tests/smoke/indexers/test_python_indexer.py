"""Smoke tests for Python symbol indexing."""

from __future__ import annotations

from app.indexer.python_indexer import index_python_symbols


def test_index_python_symbols_finds_class_and_function(sample_repo):
    symbols = index_python_symbols(sample_repo)
    names = {item["qualified_name"] for item in symbols}
    assert "Example" in names
    assert "Example.ping" in names
    assert "add" in names
