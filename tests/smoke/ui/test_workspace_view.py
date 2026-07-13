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

"""Smoke tests for workspace tools browser widget."""

from __future__ import annotations

from app.indexer.index_manager import IndexManager
from app.views.workspace_view import WorkspaceView


def test_workspace_view_buttons_render_output(monkeypatch, qtbot, app_config):
    manager = IndexManager(app_config)
    widget = WorkspaceView(manager)
    qtbot.addWidget(widget)

    monkeypatch.setattr(widget._controller, "format_git_summary", lambda: "Branch: main")
    monkeypatch.setattr(widget._controller, "generate_docs_draft", lambda changed_only=True: "# Docs Draft")
    monkeypatch.setattr(
        widget._controller,
        "generate_changelog_draft",
        lambda version_text=None, release_date=None, changed_only=True: "## [Unreleased] - 2026-07-08",
    )

    widget.git_summary_button.click()
    assert "Branch: main" in widget.output.toPlainText()

    widget.docs_draft_button.click()
    assert "# Docs Draft" in widget.output.toPlainText()

    widget.changelog_button.click()
    assert "## [Unreleased]" in widget.output.toPlainText()
    assert widget.save_output_button.isEnabled()
