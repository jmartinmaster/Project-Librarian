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

"""Smoke tests for Python symbol indexing."""

from __future__ import annotations

from app.indexer.python_indexer import index_python_symbols


def test_index_python_symbols_finds_class_and_function(sample_repo):
    symbols = index_python_symbols(sample_repo)
    names = {item["qualified_name"] for item in symbols}
    assert "Example" in names
    assert "Example.ping" in names
    assert "add" in names


def test_index_python_symbols_cst_finds_class_and_function(sample_repo):
    symbols = index_python_symbols(sample_repo, use_cst=True)
    names = {item["qualified_name"] for item in symbols}
    assert "Example" in names
    assert "Example.ping" in names
    assert "add" in names


def test_index_python_symbols_cst_matches_ast(sample_repo):
    symbols_ast = index_python_symbols(sample_repo, use_cst=False)
    symbols_cst = index_python_symbols(sample_repo, use_cst=True)
    
    symbols_ast_sorted = sorted(symbols_ast, key=lambda x: x["qualified_name"])
    symbols_cst_sorted = sorted(symbols_cst, key=lambda x: x["qualified_name"])
    
    assert len(symbols_ast_sorted) == len(symbols_cst_sorted)
    for ast_sym, cst_sym in zip(symbols_ast_sorted, symbols_cst_sorted):
        assert ast_sym["name"] == cst_sym["name"]
        assert ast_sym["qualified_name"] == cst_sym["qualified_name"]
        assert ast_sym["kind"] == cst_sym["kind"]
        assert ast_sym["line"] == cst_sym["line"]
        assert ast_sym["path"] == cst_sym["path"]
        assert ast_sym["signature"].replace(" ", "") == cst_sym["signature"].replace(" ", "")

