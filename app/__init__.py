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

"""Standalone Project Librarian application package."""

APP_NAME = "Project Librarian"
APP_COPYRIGHT = "Copyright (C) 2026 Project Librarian contributors"
APP_LICENSE_NAME = "GNU General Public License v3.0 or later"
PYQT_ATTRIBUTION = (
	"Built with PyQt6. PyQt6 is available from Riverbank Computing under GPL and commercial licensing terms."
)
STARTUP_INDEX_NOTE = (
	"If no saved project root is configured yet, indexing starts from the folder where the application is opened."
)


def build_about_text() -> str:
	"""Return the application About text shown in the desktop UI."""
	return "\n\n".join(
		[
			APP_NAME,
			"Local desktop index and search tool for source files and spreadsheets.",
			STARTUP_INDEX_NOTE,
			f"License: {APP_LICENSE_NAME}.",
			PYQT_ATTRIBUTION,
			APP_COPYRIGHT,
		]
	)
