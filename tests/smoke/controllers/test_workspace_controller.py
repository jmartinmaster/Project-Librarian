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

"""Smoke tests for WorkspaceController."""

from __future__ import annotations

from app.controllers.workspace_controller import WorkspaceController
from app.indexer.index_manager import IndexManager


def test_workspace_controller_delegates_to_model(app_config, monkeypatch, tmp_path):
    manager = IndexManager(app_config)
    controller = WorkspaceController(index_manager=manager)

    # Mock service methods to track delegation
    called: dict[str, object] = {}

    def mock_format_git_summary():
        called["format_git_summary"] = True
        return "summary"

    def mock_generate_docs_draft(changed_only):
        called["generate_docs_draft"] = changed_only
        return "docs"

    def mock_generate_changelog_draft(version_text, changed_only):
        called["generate_changelog_draft"] = (version_text, changed_only)
        return "changelog"

    monkeypatch.setattr(controller.service, "format_git_summary", mock_format_git_summary)
    monkeypatch.setattr(controller.service, "generate_docs_draft", mock_generate_docs_draft)
    monkeypatch.setattr(controller.service, "generate_changelog_draft", mock_generate_changelog_draft)

    assert controller.format_git_summary() == "summary"
    assert called.get("format_git_summary") is True

    assert controller.generate_docs_draft(changed_only=True) == "docs"
    assert called.get("generate_docs_draft") is True

    assert controller.generate_changelog_draft(version_text="1.0.0", changed_only=False) == "changelog"
    assert called.get("generate_changelog_draft") == ("1.0.0", False)


def test_workspace_controller_save_output_to_file(app_config, tmp_path):
    manager = IndexManager(app_config)
    controller = WorkspaceController(index_manager=manager)

    target_file = tmp_path / "output.md"
    controller.save_output_to_file(str(target_file), "test content")

    assert target_file.read_text(encoding="utf-8") == "test content\n"
