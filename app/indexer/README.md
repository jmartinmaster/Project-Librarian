<!--
Copyright (C) 2026 Project Librarian contributors

This file is part of Project Librarian.

Project Librarian is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Project Librarian is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.
-->

# Indexer Package

This package contains model-layer indexing logic for Python, C, and Excel content.

Modules:
- python_indexer.py: Python AST symbol extraction.
- c_indexer.py: C symbol extraction with pycparser.
- excel_indexer.py: Spreadsheet keyword record extraction.
- index_manager.py: Orchestrates indexing runs and output persistence.
