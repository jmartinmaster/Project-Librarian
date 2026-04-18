"""Smoke tests for C symbol indexing."""

from __future__ import annotations

from app.indexer.c_indexer import index_c_symbols


def test_index_c_symbols_finds_struct_and_function(sample_repo):
    symbols = index_c_symbols(sample_repo)
    kinds = {(item["kind"], item["name"]) for item in symbols}
    assert ("c_struct", "person") in kinds
    assert ("c_function", "sum") in kinds
