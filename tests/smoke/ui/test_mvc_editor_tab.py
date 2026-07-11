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

"""Smoke tests for embedded MVC editor tab."""

from __future__ import annotations

from pathlib import Path

from app.ui.mvc_editor_tab import MVCEditorTab


def test_mvc_editor_tab_exposes_model_view_controller_tabs(qtbot):
    widget = MVCEditorTab()
    qtbot.addWidget(widget)

    tab_titles = [widget.editor_tabs.tabText(index) for index in range(widget.editor_tabs.count())]
    assert tab_titles == ["MVC Editor"]


def test_mvc_editor_tab_loads_and_saves_triad(qtbot, tmp_path: Path):
    workspace = tmp_path / "mvc_editor"
    (workspace / "app" / "models").mkdir(parents=True)
    (workspace / "app" / "views").mkdir(parents=True)
    (workspace / "app" / "controllers").mkdir(parents=True)

    model_file = workspace / "app" / "models" / "model.py"
    view_file = workspace / "app" / "views" / "view.py"
    controller_file = workspace / "app" / "controllers" / "controller.py"
    model_file.write_text("class DocumentModel:\n    pass\n", encoding="utf-8")
    view_file.write_text("class EditorView:\n    pass\n", encoding="utf-8")
    controller_file.write_text("class EditorController:\n    pass\n", encoding="utf-8")
    entrypoint = workspace / "main.py"
    entrypoint.write_text(
        "from app.models.model import DocumentModel\n"
        "from app.views.view import EditorView\n"
        "from app.controllers.controller import EditorController\n",
        encoding="utf-8",
    )

    widget = MVCEditorTab(workspace_root=str(workspace))
    qtbot.addWidget(widget)
    widget.open_file(entrypoint)

    assert "DocumentModel" in widget.model_editor.toPlainText()
    assert "EditorView" in widget.view_editor.toPlainText()
    assert "EditorController" in widget.controller_editor.toPlainText()

    widget.model_editor.setPlainText("class DocumentModel:\n    value = 1\n")
    widget.save_triad()
    assert "value = 1" in model_file.read_text(encoding="utf-8")


def test_mvc_editor_tab_opens_saves_and_launches_current_file(monkeypatch, qtbot, tmp_path: Path):
    target = tmp_path / "single_file.py"
    target.write_text("line1\nline2\nline3\n", encoding="utf-8")

    widget = MVCEditorTab(workspace_root=str(tmp_path))
    qtbot.addWidget(widget)

    opened = widget.open_file(target, line_number=2)
    assert opened
    assert widget.current_file_edit.text().endswith("single_file.py")
    assert widget.editor_tabs.tabText(widget.editor_tabs.currentIndex()) == "MVC Editor"

    widget.file_editor.setPlainText("updated\ncontent\n")
    widget.save_current_file()
    assert "updated" in target.read_text(encoding="utf-8")

    external_calls: dict[str, str] = {}

    def fake_open(url):
        external_calls["path"] = url.toLocalFile()
        return True

    monkeypatch.setattr("app.ui.mvc_editor_tab.QDesktopServices.openUrl", fake_open)
    widget.open_current_externally()
    assert external_calls["path"].endswith("single_file.py")


def test_mvc_editor_tab_trigger_local_ai(monkeypatch, qtbot):
    """Test that clicking the Trigger Local AI button saves file and calls controller run_ai_generation."""
    widget = MVCEditorTab()
    qtbot.addWidget(widget)

    ai_called = False
    def mock_run_ai(callback):
        nonlocal ai_called
        ai_called = True
        callback(True, "AI Generation complete")

    monkeypatch.setattr(widget._controller, "run_ai_generation", mock_run_ai)
    monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.information", lambda *args: None)

    widget.trigger_ai_button.click()
    assert ai_called is True
    assert "AI Generation complete" in widget.status_label.text()

