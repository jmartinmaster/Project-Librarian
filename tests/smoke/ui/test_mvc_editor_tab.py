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
"""Smoke tests for embedded MVC editor tab."""

from __future__ import annotations

from pathlib import Path

from app.views.mvc_editor_tab import MVCEditorTab


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
    with qtbot.waitSignal(widget._controller.triad_loaded, timeout=5000):
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

    with qtbot.waitSignal(widget._controller.triad_loaded, timeout=5000):
        opened = widget.open_file(target, line_number=2)
    assert opened
    assert widget.current_file_edit.text().endswith("single_file.py")
    assert widget.editor_tabs.tabText(widget.editor_tabs.currentIndex()) == "MVC Editor"

    widget.file_editor.setPlainText("updated\ncontent\n")
    widget.save_current_file()
    assert "updated" in target.read_text(encoding="utf-8")
    widget.save_current_file()
    assert "updated" in target.read_text(encoding="utf-8")

    external_calls: dict[str, str] = {}

    def fake_open(url):
        external_calls["path"] = url.toLocalFile()
        return True

    monkeypatch.setattr("app.views.mvc_editor_tab.QDesktopServices.openUrl", fake_open)
    widget.open_current_externally()
    assert external_calls["path"].endswith("single_file.py")


def test_mvc_editor_tab_autocomplete(qtbot):
    widget = MVCEditorTab()
    qtbot.addWidget(widget)
    
    assert widget.model_editor.completer() is not None
    assert widget.view_editor.completer() is not None
    assert widget.controller_editor.completer() is not None
    
    model = widget.model_editor.completer().model()
    words = [model.index(i, 0).data() for i in range(model.rowCount())]
    assert "class" in words
    assert "QWidget" in words


def test_mvc_editor_tab_create_triad(qtbot, tmp_path: Path):
    workspace = tmp_path / "mvc_workspace"
    workspace.mkdir()
    
    widget = MVCEditorTab(workspace_root=str(workspace))
    qtbot.addWidget(widget)
    
    with qtbot.waitSignal(widget._controller.triad_loaded, timeout=5000):
        widget._controller.create_new_mvc_triad("DashboardWidget", str(workspace))

    assert (workspace / "models" / "dashboard_widget_model.py").exists()
    assert (workspace / "views" / "dashboard_widget_view.py").exists()
    assert (workspace / "controllers" / "dashboard_widget_controller.py").exists()

    assert "class DashboardWidgetModel(QObject):" in widget.model_editor.toPlainText()
    assert "class DashboardWidgetView(QWidget):" in widget.view_editor.toPlainText()
    assert "class DashboardWidgetController:" in widget.controller_editor.toPlainText()


def test_mvc_editor_tab_cst_method_ranges():
    from app.config import AppConfig
    from app.views.mvc_sync.model import DocumentModel

    config = AppConfig(use_cst=True)
    model = DocumentModel(config=config)

    content = (
        "class Dummy:\n"
        "    # Comment 1\n"
        "    def method_1(self):\n"
        "        pass\n"
        "        # Comment 2"
    )

    # 1. Parse with use_cst = True
    model.parse_outline("model", content)
    outline_cst = model.get_outline("model")

    assert outline_cst is not None
    assert len(outline_cst["classes"]) == 1
    dummy_class = outline_cst["classes"][0]
    assert dummy_class["name"] == "Dummy"
    assert len(dummy_class["methods"]) == 1
    method_1 = dummy_class["methods"][0]
    assert method_1["name"] == "method_1"

    # Range should include Comment 1 (line 2) and Comment 2 (line 5)
    assert method_1["start_line"] == 2
    assert method_1["end_line"] == 6

    # 2. Parse with use_cst = False
    config.use_cst = False
    model.parse_outline("model", content)
    outline_ast = model.get_outline("model")

    assert outline_ast is not None
    method_ast = outline_ast["classes"][0]["methods"][0]
    assert method_ast["name"] == "method_1"
    # Range should only include standard AST statements (line 3 to line 4)
    assert method_ast["start_line"] == 3
    assert method_ast["end_line"] == 4


def test_mvc_editor_tab_live_formatting_highlights(qtbot, tmp_path: Path):
    from app.views.mvc_editor_tab import MVCEditorTab
    
    # Create a workspace with a python file containing formatting issues
    workspace = tmp_path / "workspace"
    (workspace / "app" / "models").mkdir(parents=True)
    (workspace / "app" / "views").mkdir(parents=True)
    (workspace / "app" / "controllers").mkdir(parents=True)
    
    model_file = workspace / "app" / "models" / "dashboard_model.py"
    view_file = workspace / "app" / "views" / "dashboard_view.py"
    controller_file = workspace / "app" / "controllers" / "dashboard_controller.py"
    
    model_file.write_text("x = (1 + 2\n", encoding="utf-8")
    view_file.write_text("class DashboardView:\n    pass\n", encoding="utf-8")
    controller_file.write_text("class DashboardController:\n    pass\n", encoding="utf-8")
    
    tab = MVCEditorTab(workspace_root=str(workspace))
    qtbot.addWidget(tab)
    
    with qtbot.waitSignal(tab._controller.triad_loaded, timeout=5000):
        tab.open_file(model_file)
        
    editor = tab.model_editor
    # Wait for the live lint worker thread to complete
    qtbot.waitUntil(lambda: len(editor.diagnostics) > 0, timeout=5000)

    
    # Verify formatting diagnostics are loaded
    assert len(editor.diagnostics) > 0
    assert any(d["preset_name"] == "Formatting: Unclosed Bracket" for d in editor.diagnostics)
    
    # Verify extra selections/highlights have been rendered
    assert len(editor.extraSelections()) > 0

    # Move cursor to line 1 (the error line) and assert status label is updated
    editor.setProperty("test_mode", True)
    editor._on_cursor_position_changed()
    assert "Formatting: Unclosed Bracket" in tab.status_label.text()





