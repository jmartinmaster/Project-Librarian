# Copyright (C) 2026 The Librarian contributors
#
# This file is part of The Librarian.
#
# The Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with The Librarian. If not, see <https://www.gnu.org/licenses/>.
"""Smoke tests for workspace service summaries and draft generation."""

from __future__ import annotations

from app.indexer.index_manager import IndexManager
from app.models.workspace_model import WorkspaceModel


def test_workspace_model_formats_git_summary(monkeypatch, app_config):
    manager = IndexManager(app_config)
    service = WorkspaceModel(index_manager=manager)

    snapshot = {
        "branch": "feature/test",
        "changed_files": [
            {"status": "M", "path": "app/main.py", "area": "app"},
            {"status": "??", "path": "docs/notes.md", "area": "docs"},
        ],
        "status_counts": {"??": 1, "M": 1},
        "area_counts": {"app": 1, "docs": 1},
        "recent_commits": [{"short_commit": "abc123", "date": "2026-07-08", "subject": "Add feature", "author": "Jamie"}],
    }
    monkeypatch.setattr(service, "collect_git_snapshot", lambda commit_limit=5: snapshot)

    text = service.format_git_summary()
    assert "Branch: feature/test" in text
    assert "Changed Files: 2" in text
    assert "app/main.py" in text
    assert "Add feature" in text


def test_workspace_model_generates_docs_and_changelog(monkeypatch, app_config):
    manager = IndexManager(app_config)
    manager.state.file_corpus = {"app/sample.py": "def alpha():\n    return 1\n"}
    manager.state.symbols = [{"path": "app/sample.py", "name": "alpha", "qualified_name": "alpha"}]

    service = WorkspaceModel(index_manager=manager)
    monkeypatch.setattr(
        service,
        "collect_git_snapshot",
        lambda commit_limit=5: {
            "branch": "main",
            "changed_files": [{"status": "M", "path": "app/sample.py", "area": "app"}],
            "status_counts": {"M": 1},
            "area_counts": {"app": 1},
            "recent_commits": [{"subject": "Touch sample"}],
        },
    )

    docs_draft = service.generate_docs_draft(changed_only=True)
    changelog = service.generate_changelog_draft(version_text="1.2.3", changed_only=True)

    assert "Project Documentation Update Draft" in docs_draft
    assert "app/sample.py" in docs_draft
    assert "## [1.2.3]" in changelog
    assert "Files considered: 1" in changelog
