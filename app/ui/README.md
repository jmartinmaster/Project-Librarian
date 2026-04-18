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

# UI Package

This package contains PyQt6 view/controller components.

Rules:
- Keep business logic out of UI widgets.
- Use index_manager and search_engine from controller code paths.
- Keep layout changes in Qt Designer form files under app/ui/forms/.
- Load .ui files at runtime using PyQt6 uic.loadUi so manual UI edits do not require code regeneration.
