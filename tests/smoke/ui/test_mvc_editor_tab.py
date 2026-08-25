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
    widget.mode_combo.setCurrentText("Triad (MVC)")
    with qtbot.waitSignal(widget._controller.triad_loaded, timeout=5000):
        widget.open_file(entrypoint)

    assert "DocumentModel" in widget.model_editor.toPlainText()
    assert "EditorView" in widget.view_editor.toPlainText()
    assert "EditorController" in widget.controller_editor.toPlainText()

    widget.model_editor.setPlainText("class DocumentModel:\n    value = 1\n")
    widget.save_triad()
    assert "value = 1" in model_file.read_text(encoding="utf-8")


def test_mvc_editor_tab_single_vs_triad_mode_toggle(qtbot, tmp_path: Path):
    target = tmp_path / "standalone.py"
    target.write_text("x = 42\n", encoding="utf-8")

    widget = MVCEditorTab(workspace_root=str(tmp_path))
    qtbot.addWidget(widget)

    # Starts in Single File mode
    assert widget.mode_combo.currentText() == "Single File"
    widget.open_file(target)
    assert widget.controller_editor.toPlainText().strip() == "x = 42"
    assert not widget._view.controller_pane.isHidden()
    assert widget._view.model_pane.isHidden()
    assert widget._view.view_pane.isHidden()
    assert widget._view.inspector_widget.isHidden()

    # Switch to Triad mode
    widget.mode_combo.setCurrentText("Triad (MVC)")
    assert not widget._view.controller_pane.isHidden()
    assert not widget._view.model_pane.isHidden()
    assert not widget._view.view_pane.isHidden()
    assert not widget._view.inspector_widget.isHidden()


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
    tab.mode_combo.setCurrentText("Triad (MVC)")
    
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


def test_mvc_editor_tab_cpp_syntax_highlighting(qtbot, tmp_path: Path):
    from app.views.mvc_sync.editor import CppHighlighter, PythonHighlighter
    c_file = tmp_path / "peripheral.c"
    c_file.write_text("#include <stdio.h>\nint main() { return 0; }\n", encoding="utf-8")

    tab = MVCEditorTab(workspace_root=str(tmp_path))
    qtbot.addWidget(tab)

    tab.open_file(c_file)
    # Confirm CppHighlighter is active on the editor pane
    assert isinstance(tab._view.controller_pane.highlighter, CppHighlighter)

    # Manual language switch
    tab.language_combo.setCurrentText("Python (Standard)")
    assert isinstance(tab._view.controller_pane.highlighter, PythonHighlighter)
    assert not tab._view.controller_pane.highlighter.micropython_mode

    tab.language_combo.setCurrentText("MicroPython")
    assert isinstance(tab._view.controller_pane.highlighter, PythonHighlighter)
    assert tab._view.controller_pane.highlighter.micropython_mode

    tab.language_combo.setCurrentText("C / C++")
    assert isinstance(tab._view.controller_pane.highlighter, CppHighlighter)


def test_mvc_editor_tab_jump_to_definition(qtbot, tmp_path: Path):
    from unittest.mock import MagicMock
    from app.views.mvc_editor_tab import MVCEditorTab

    helper_file = tmp_path / "helpers.py"
    helper_file.write_text("def my_special_function():\n    return 42\n", encoding="utf-8")

    main_file = tmp_path / "main.py"
    main_file.write_text("from helpers import my_special_function\nmy_special_function()\n", encoding="utf-8")

    mock_manager = MagicMock()
    mock_manager.state.symbols = [
        {"name": "my_special_function", "qualified_name": "my_special_function", "kind": "function", "path": "helpers.py", "line": 1},
    ]

    tab = MVCEditorTab(workspace_root=str(tmp_path), index_manager=mock_manager)
    qtbot.addWidget(tab)

    tab.open_file(main_file)
    assert tab._current_file_path.name == "main.py"

    # Request jump to definition
    ok = tab.jump_to_symbol_definition("my_special_function")
    assert ok is True
    assert tab._current_file_path.name == "helpers.py"


def test_cst_ranges_with_blank_lines_and_class_docstring(qtbot):
    from app.config import AppConfig
    from app.views.mvc_sync.model import DocumentModel

    config = AppConfig(use_cst=True)
    model = DocumentModel(config=config)

    content = (
        "import os\n"
        "\n"
        "# Class comment\n"
        "class MyView:\n"
        '    """Class docstring."""\n'
        "\n"
        "    # Method comment\n"
        "    def __init__(self):\n"
        "        self.x = 1\n"
        "\n"
        "    def render(self):\n"
        "        pass\n"
    )
    model.parse_outline("view", content)
    outline = model.get_outline("view")

    assert outline is not None
    assert outline["is_cst"] is True
    cls = outline["classes"][0]
    assert cls["name"] == "MyView"
    assert cls["line"] == 4  # exact 'class MyView' line
    assert cls["start_line"] == 3  # '# Class comment'
    assert cls["end_line"] == 12

    init_m = cls["methods"][0]
    assert init_m["name"] == "__init__"
    assert init_m["line"] == 8  # exact 'def __init__' line
    assert init_m["start_line"] == 7  # '# Method comment' (does not include blank line 6)
    assert init_m["end_line"] == 9

    render_m = cls["methods"][1]
    assert render_m["name"] == "render"
    assert render_m["line"] == 11
    assert render_m["start_line"] == 11  # does not include blank line 10
    assert render_m["end_line"] == 12

    # Verify active block range when cursor is on docstring (line 5)
    docstring_range = model.get_active_block_range("view", 5)
    assert docstring_range == (3, 6)  # Class header before first method

    # Verify active block range when cursor is on __init__ (line 8)
    init_range = model.get_active_block_range("view", 8)
    assert init_range == (7, 9)

    # Verify active block range when cursor is on render (line 11)
    render_range = model.get_active_block_range("view", 11)
    assert render_range == (11, 12)


def test_mvc_sync_inspector_tabs_and_symbol_subtabs(qtbot):
    widget = MVCEditorTab()
    qtbot.addWidget(widget)

    # Check top-level inspector tabs
    assert widget.inspector_tabs.count() == 2
    assert widget.inspector_tabs.tabText(0) == "Connections"
    assert widget.inspector_tabs.tabText(1) == "Symbols"

    # Check inner symbols subtabs (one for each triad role)
    assert widget.symbols_tab_widget.count() == 3
    assert widget.symbols_tab_widget.tabText(0) == "Model"
    assert widget.symbols_tab_widget.tabText(1) == "View"
    assert widget.symbols_tab_widget.tabText(2) == "Controller"


def test_mvc_sync_inspector_symbols_listing_and_double_click_jump(qtbot, tmp_path: Path):
    workspace = tmp_path / "mvc_symbols_test"
    (workspace / "models").mkdir(parents=True)
    (workspace / "views").mkdir(parents=True)
    (workspace / "controllers").mkdir(parents=True)

    model_code = (
        "from PyQt6.QtCore import QObject, pyqtSignal\n\n"
        "class CounterModel(QObject):\n"
        "    count_changed = pyqtSignal(int)\n"
        "    MAX_COUNT = 100\n\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self._count = 0\n\n"
        "    @property\n"
        "    def count(self) -> int:\n"
        "        return self._count\n\n"
        "    def increment(self):\n"
        "        self._count += 1\n"
        "        self.count_changed.emit(self._count)\n"
    )
    (workspace / "models" / "counter_model.py").write_text(model_code, encoding="utf-8")
    (workspace / "views" / "counter_view.py").write_text("class CounterView:\n    pass\n", encoding="utf-8")
    (workspace / "controllers" / "counter_controller.py").write_text("class CounterController:\n    pass\n", encoding="utf-8")

    widget = MVCEditorTab(workspace_root=str(workspace))
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget._controller.triad_loaded, timeout=5000):
        widget.open_file(str(workspace / "models" / "counter_model.py"))

    # Verify Model symbols list is populated
    model_list = widget.model_symbols_list
    qtbot.waitUntil(lambda: model_list.count() >= 5, timeout=5000)

    # Check widget types and names
    extracted_names = []
    for i in range(model_list.count()):
        item = model_list.item(i)
        w = model_list.itemWidget(item)
        if hasattr(w, "item_info"):
            extracted_names.append((w.item_info.get("type"), w.item_info.get("name")))

    types = [t for t, n in extracted_names]
    names = [n for t, n in extracted_names]
    assert "class" in types
    assert "CounterModel" in names
    assert "signal" in types
    assert "count_changed" in names
    assert "declaration" in types
    assert "MAX_COUNT" in names
    assert "property" in types
    assert "count" in names
    assert "method" in types
    assert "increment" in names

    # Double click on increment method item and verify editor cursor and highlight
    inc_item_idx = next(i for i, (t, n) in enumerate(extracted_names) if n == "increment")
    item = model_list.item(inc_item_idx)
    model_list.itemDoubleClicked.emit(item)

    assert widget.model_editor.block_start_line is not None
    assert widget.model_editor.block_end_line is not None
    assert widget.model_editor.textCursor().blockNumber() + 1 >= widget.model_editor.block_start_line

    # Test symbol filter box
    widget.symbol_filter_input.setText("increment")
    assert model_list.item(inc_item_idx).isHidden() is False
    # Check that non-matching items are hidden
    for i in range(model_list.count()):
        if i != inc_item_idx:
            w = model_list.itemWidget(model_list.item(i))
            if hasattr(w, "item_info") and "increment" not in str(w.item_info.get("name", "")).lower():
                assert model_list.item(i).isHidden() is True

    # Clear filter
    widget.symbol_filter_input.setText("")
    for i in range(model_list.count()):
        assert model_list.item(i).isHidden() is False


