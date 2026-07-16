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
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QPlainTextEdit, QTextEdit, QCompleter, QToolTip
)
from PyQt6.QtGui import QPainter, QTextCharFormat, QColor, QFont, QSyntaxHighlighter, QTextFormat, QTextCursor
from PyQt6.QtCore import QSize, Qt, QRect, QRegularExpression, pyqtSignal, QThread, QTimer

class PythonHighlighter(QSyntaxHighlighter):
    """
    Custom QSyntaxHighlighter for Python code, styled for the Catppuccin theme.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Catppuccin theme colors
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#cba6f7"))  # Lavender
        keyword_format.setFontWeight(QFont.Weight.Bold)

        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#89b4fa"))  # Blue

        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#f9e2af"))  # Yellow
        class_format.setFontWeight(QFont.Weight.Bold)

        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#89dceb"))  # Sky / Cyan
        function_format.setFontItalic(True)

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6c7086"))  # Muted grey-blue
        comment_format.setFontItalic(True)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#a6e3a1"))  # Green

        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#fab387"))  # Peach

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#f5a97f"))  # Soft orange

        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#94e2d5"))  # Teal

        call_format = QTextCharFormat()
        call_format.setForeground(QColor("#89dceb"))  # Sky

        self_format = QTextCharFormat()
        self_format.setForeground(QColor("#fab387"))  # Peach
        self_format.setFontItalic(True)

        # 1. Function calls and operators (added first so keywords can override them)
        self.highlighting_rules.append((QRegularExpression(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()"), call_format))
        self.highlighting_rules.append((QRegularExpression(r"[\+\-\*\/\%\=\!\<\>\&\|\^\~]"), operator_format))

        # Python keywords
        keywords = [
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "class", "continue", "def", "del", "elif", "else",
            "except", "finally", "for", "from", "global", "if", "import",
            "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
            "return", "try", "while", "with", "yield"
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.highlighting_rules.append((pattern, keyword_format))

        # Common builtins
        builtins = ["print", "len", "range", "str", "int", "float", "list", 
                    "dict", "set", "tuple", "super", "open", "Exception"]
        for word in builtins:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.highlighting_rules.append((pattern, builtin_format))

        # self parameter
        self.highlighting_rules.append((QRegularExpression(r"\bself\b"), self_format))

        # Comments
        self.highlighting_rules.append((QRegularExpression(r"#[^\n]*"), comment_format))

        # Class names: class ClassName
        self.highlighting_rules.append((QRegularExpression(r"\bclass\s+([a-zA-Z0-9_]+)"), class_format))

        # Function names: def func_name
        self.highlighting_rules.append((QRegularExpression(r"\bdef\s+([a-zA-Z0-9_]+)"), function_format))

        # Decorators: @decorator
        self.highlighting_rules.append((QRegularExpression(r"@[a-zA-Z0-9_]+"), decorator_format))

        # Numbers
        self.highlighting_rules.append((QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format))

        # Strings
        self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'), string_format))
        self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(?:\\.[^'\\]*)*'"), string_format))

        # Triple quote regexes for multi-line string highlighting
        self.tri_single = QRegularExpression(r"'''")
        self.tri_double = QRegularExpression(r'"""')
        self.multi_line_string_format = string_format

    def highlightBlock(self, text):
        # 1. Apply single-line patterns
        for pattern, fmt in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                if pattern.captureCount() > 0:
                    start = match.capturedStart(1)
                    length = match.capturedLength(1)
                else:
                    start = match.capturedStart()
                    length = match.capturedLength()
                self.setFormat(start, length, fmt)

        # 2. State-machine based triple-quote parser
        state = self.previousBlockState()
        if state < 0:
            state = 0

        index = 0
        while index < len(text):
            if state == 0:
                match_db = self.tri_double.match(text, index)
                match_sg = self.tri_single.match(text, index)
                
                db_idx = match_db.capturedStart() if match_db.hasMatch() else -1
                sg_idx = match_sg.capturedStart() if match_sg.hasMatch() else -1
                
                if db_idx != -1 and (sg_idx == -1 or db_idx < sg_idx):
                    state = 1
                    index = db_idx
                elif sg_idx != -1 and (db_idx == -1 or sg_idx < db_idx):
                    state = 2
                    index = sg_idx
                else:
                    break
            
            if state == 1:  # Inside """
                end_match = self.tri_double.match(text, index + 3)
                if end_match.hasMatch():
                    end_idx = end_match.capturedStart()
                    self.setFormat(index, end_idx - index + 3, self.multi_line_string_format)
                    index = end_idx + 3
                    state = 0
                else:
                    self.setFormat(index, len(text) - index, self.multi_line_string_format)
                    break
            elif state == 2:  # Inside '''
                end_match = self.tri_single.match(text, index + 3)
                if end_match.hasMatch():
                    end_idx = end_match.capturedStart()
                    self.setFormat(index, end_idx - index + 3, self.multi_line_string_format)
                    index = end_idx + 3
                    state = 0
                else:
                    self.setFormat(index, len(text) - index, self.multi_line_string_format)
                    break
                    
        self.setCurrentBlockState(state)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class LiveLintWorker(QThread):
    """Background worker to check file formatting rules live."""
    finished_signal = pyqtSignal(list)

    def __init__(self, file_path: str, content: str) -> None:
        super().__init__()
        self.file_path = file_path
        self.content = content

    def run(self) -> None:
        from app.models.format_checker import FormatChecker
        try:
            results = FormatChecker.check_format(self.file_path, self.content)
            self.finished_signal.emit(results)
        except Exception:
            self.finished_signal.emit([])


class PyCodeEditor(QPlainTextEdit):
    """
    Custom Code Editor widget incorporating Python Syntax Highlighting,
    line number painting, tab-to-spaces auto-handling, auto-indentation,
    and current line highlighting.
    """
    ai_request_triggered = pyqtSignal()
    diagnostic_hovered = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.line_number_area = LineNumberArea(self)
        self.target_line = None
        self.target_highlight_color = QColor("#3e302f")
        self.block_start_line = None
        self.block_end_line = None
        self.block_highlight_color = QColor("#181825")
        self._completer = None
        self.current_file_path = None
        self.diagnostics = []

        self._lint_timer = QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.timeout.connect(self._run_live_lint)
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)

        # Style font
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # Colors & Layout
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                selection-background-color: #45475a;
                selection-color: #f5c2e7;
            }
        """)

        # Connect slots
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val /= 10
            digits += 1
        space = 18 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#181825"))  # Muted background for sidebar

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        painter.setFont(self.font())
        text_color = QColor("#585b70")
        active_color = QColor("#cba6f7")
        cursor_block_num = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == cursor_block_num:
                    painter.setPen(active_color)
                else:
                    painter.setPen(text_color)
                painter.drawText(
                    0, top, self.line_number_area.width() - 8, self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, number
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        
        # 1. Block range highlight (for the active method/class) - lowest layer
        block_start = getattr(self, 'block_start_line', None)
        block_end = getattr(self, 'block_end_line', None)
        if block_start is not None and block_end is not None:
            doc = self.document()
            for l in range(block_start, block_end + 1):
                block = doc.findBlockByLineNumber(l - 1)
                if block.isValid():
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(self.block_highlight_color)
                    selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                    
                    cursor = self.textCursor()
                    cursor.setPosition(block.position())
                    cursor.clearSelection()
                    selection.cursor = cursor
                    
                    extra_selections.append(selection)

        # 2. Subtle current line cursor highlight - middle layer
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            
            # Check if active line has live formatting diagnostics
            active_line = self.textCursor().blockNumber() + 1
            line_color = QColor("#252636")  # Default subtle active-line highlight
            
            line_diags = [d for d in getattr(self, "diagnostics", []) if d.get("line") == active_line]
            if line_diags:
                severity = str(line_diags[0].get("severity", "")).lower()
                if severity == "error":
                    line_color = QColor("#3e262c")  # Soft red for error lines
                elif severity == "warning":
                    line_color = QColor("#3c3224")  # Soft amber/orange for warnings
                else:
                    line_color = QColor("#222d3d")  # Soft blue for info checks
                    
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
            
        # 3. Bright target line highlight - top layer
        if getattr(self, 'target_line', None) is not None:
            doc = self.document()
            block = doc.findBlockByLineNumber(self.target_line - 1)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.format.setBackground(self.target_highlight_color)
                selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                
                cursor = self.textCursor()
                cursor.setPosition(block.position())
                cursor.clearSelection()
                selection.cursor = cursor
                
                extra_selections.append(selection)

        # 4. Formatting Diagnostics Highlight (Wavy underlays)
        if getattr(self, 'diagnostics', None):
            doc = self.document()
            for diag in self.diagnostics:
                line_num = diag.get("line")
                if not isinstance(line_num, int):
                    continue
                block = doc.findBlockByLineNumber(line_num - 1)
                if block.isValid():
                    selection = QTextEdit.ExtraSelection()
                    
                    # Style wavy underline
                    severity = str(diag.get("severity", "")).lower()
                    if severity == "error":
                        selection.format.setUnderlineColor(QColor("#f38ba8"))
                    elif severity == "warning":
                        selection.format.setUnderlineColor(QColor("#f9e2af"))
                    else:
                        selection.format.setUnderlineColor(QColor("#89b4fa"))
                    
                    selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
                    
                    # Highlight target word if match text is found
                    text = block.text()
                    match_text = str(diag.get("match", ""))
                    
                    cursor = self.textCursor()
                    if match_text and match_text in text:
                        start_idx = text.find(match_text)
                        cursor.setPosition(block.position() + start_idx)
                        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(match_text))
                    else:
                        cursor.setPosition(block.position())
                        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                        
                    selection.cursor = cursor
                    extra_selections.append(selection)
                    
        self.setExtraSelections(extra_selections)

    def _on_text_changed(self) -> None:
        if self.current_file_path:
            self._lint_timer.start(500)

    def _run_live_lint(self) -> None:
        if not self.current_file_path:
            return
        content = self.toPlainText()
        self._lint_worker = LiveLintWorker(self.current_file_path, content)
        self._lint_worker.finished_signal.connect(self._on_live_lint_finished)
        self._lint_worker.start()

    def _on_live_lint_finished(self, results: list[dict[str, object]]) -> None:
        self.diagnostics = results
        self.highlight_current_line()

    def highlight_target_line(self, line: int, color_hex: str = "#3e302f"):
        self.target_line = line
        self.target_highlight_color = QColor(color_hex)
        self.highlight_current_line()

    def _on_cursor_position_changed(self) -> None:
        if not (self.hasFocus() or self.property("test_mode")):
            return
        cursor = self.textCursor()
        line_number = cursor.blockNumber() + 1
        path_str = self.current_file_path or ""
        hovered_diags = [d for d in self.diagnostics if d.get("line") == line_number]
        if hovered_diags:
            text = "; ".join([f"[{d.get('preset_name', '')}] {d.get('description', '')}" for d in hovered_diags])
            self.diagnostic_hovered.emit(text, path_str)
        else:
            self.diagnostic_hovered.emit("", path_str)

    def mousePressEvent(self, event):
        # Clear target line highlight on manual mouse clicks
        self.target_line = None
        self.highlight_current_line()
        super().mousePressEvent(event)

    def setCompleter(self, completer: QCompleter) -> None:
        if self._completer:
            self._completer.activated.disconnect()
        self._completer = completer
        if not self._completer:
            return
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated.connect(self.insertCompletion)

    def completer(self) -> QCompleter | None:
        return self._completer

    def insertCompletion(self, completion: str) -> None:
        if not self._completer or self._completer.widget() is not self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(tc.MoveOperation.Left, tc.MoveOperation.KeepAnchor, len(self._completer.completionPrefix()))
        tc.removeSelectedText()
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self) -> str:
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        return tc.selectedText()

    def focusInEvent(self, event) -> None:
        if self._completer:
            self._completer.setWidget(self)
        super().focusInEvent(event)

    def keyPressEvent(self, event) -> None:
        # Clear target line highlight on manual typing
        self.target_line = None
        self.highlight_current_line()

        if self._completer and self._completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.ignore()
                return

        isAIShortcut = (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_I
        if isAIShortcut:
            self.ai_request_triggered.emit()
            event.accept()
            return

        isShortcut = (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_Space
        if not self._completer or not isShortcut:
            # Override Tab to insert 4 spaces
            if event.key() == Qt.Key.Key_Tab:
                self.insertPlainText("    ")
                return

            # Override Enter for smart indentation
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                cursor = self.textCursor()
                current_block = cursor.block()
                text = current_block.text()
                indent = ""
                for char in text:
                    if char.isspace():
                        indent += char
                    else:
                        break
                if text.strip().endswith(':'):
                    indent += "    "
                super().keyPressEvent(event)
                self.insertPlainText(indent)
                return

            # Auto-closing parenthesis and quote pairs
            auto_pairs = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}
            if event.text() in auto_pairs:
                char = event.text()
                close_char = auto_pairs[char]
                cursor = self.textCursor()
                next_char = self.document().characterAt(cursor.position())
                if char in ('"', "'") and next_char == char:
                    cursor.movePosition(cursor.MoveOperation.NextCharacter)
                    self.setTextCursor(cursor)
                    return
                super().keyPressEvent(event)
                self.insertPlainText(close_char)
                cursor = self.textCursor()
                cursor.movePosition(cursor.MoveOperation.PreviousCharacter)
                self.setTextCursor(cursor)
                return

            super().keyPressEvent(event)

        if not self._completer:
            return

        ctrlOrShift = event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        if ctrlOrShift and event.text() == "":
            return

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        hasModifier = (event.modifiers() != Qt.KeyboardModifier.NoModifier) and not isShortcut
        completionPrefix = self.textUnderCursor()

        if not isShortcut and (hasModifier or event.text() == "" or len(completionPrefix) < 1 or event.text()[-1] in eow):
            self._completer.popup().hide()
            return

        if completionPrefix != self._completer.completionPrefix():
            self._completer.setCompletionPrefix(completionPrefix)
            self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(0) + self._completer.popup().verticalScrollBar().sizeHint().width())
        self._completer.complete(cr)


class EditorPane(QWidget):
    """
    Self-contained panel wrapping the Python editor, file metadata header,
    breadcrumb navigators, and a placeholder screen for missing files.
    """
    jump_to_line_requested = pyqtSignal(int)
    create_clicked = pyqtSignal(str) # role
    browse_clicked = pyqtSignal(str) # role
    ai_clicked = pyqtSignal(str) # role

    def __init__(self, role: str, title: str, accent_color: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.title = title
        self.accent_color = accent_color
        self._outline = {'classes': [], 'functions': []}
        
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)

        # 1. Header widget
        self.header = QWidget()
        self.header.setObjectName("EditorHeader")
        self.header.setStyleSheet(f"""
            QWidget#EditorHeader {{
                background-color: #181825;
                border-bottom: 2px solid {self.accent_color};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(4)

        row1_layout = QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(6)

        # Editor Badge
        self.badge = QLabel(self.title.upper())
        self.badge.setStyleSheet(f"""
            background-color: {self.accent_color};
            color: #11111b;
            font-weight: bold;
            font-size: 11px;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        row1_layout.addWidget(self.badge)

        # File path label
        self.file_label = QLabel("No File Loaded")
        self.file_label.setStyleSheet("color: #a6adc8; font-weight: 500; font-size: 11px;")
        row1_layout.addWidget(self.file_label)

        # Folder button to select/associate a different file
        self.browse_btn_header = QPushButton("📁")
        self.browse_btn_header.setFixedSize(18, 18)
        self.browse_btn_header.setToolTip("Select / Associate different file")
        self.browse_btn_header.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #a6adc8;
                border: none;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: #313244;
                color: {self.accent_color};
                border-radius: 3px;
            }}
        """)
        self.browse_btn_header.clicked.connect(lambda: self.browse_clicked.emit(self.role))
        row1_layout.addWidget(self.browse_btn_header)
        row1_layout.addStretch(1)

        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(4)

        # Class / Method breadcrumbs
        self.class_combo = QComboBox()
        self.class_combo.setToolTip("Active Class")
        self.class_combo.setMinimumWidth(80)
        self.class_combo.setStyleSheet("""
            QComboBox {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 1px 4px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        
        self.method_combo = QComboBox()
        self.method_combo.setToolTip("Active Method")
        self.method_combo.setMinimumWidth(100)
        self.method_combo.setStyleSheet("""
            QComboBox {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 1px 4px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)

        self.ai_btn = QPushButton("🤖 AI Edit")
        self.ai_btn.setToolTip("Process #AI-request comments in this file (Ctrl+I)")
        self.ai_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.accent_color};
                color: #11111b;
            }}
        """)
        self.ai_btn.clicked.connect(lambda: self.ai_clicked.emit(self.role))

        row2_layout.addWidget(self.class_combo)
        row2_layout.addWidget(QLabel(">"))
        row2_layout.addWidget(self.method_combo)
        row2_layout.addStretch(1)
        row2_layout.addWidget(self.ai_btn)

        header_layout.addLayout(row1_layout)
        header_layout.addLayout(row2_layout)

        self.main_layout.addWidget(self.header)

        # 2. Text Editor
        self.editor = PyCodeEditor()
        self.editor.ai_request_triggered.connect(lambda: self.ai_clicked.emit(self.role))
        self.highlighter = PythonHighlighter(self.editor.document())
        self.main_layout.addWidget(self.editor)

        # 3. Sibling Placeholder Panel
        self.placeholder = QWidget()
        self.placeholder.setStyleSheet("background-color: #11111b; border: 1px dashed #313244; border-radius: 8px;")
        placeholder_layout = QVBoxLayout(self.placeholder)
        placeholder_layout.setContentsMargins(12, 24, 12, 24)
        placeholder_layout.setSpacing(12)
        
        self.placeholder_label = QLabel(f"No {self.title} file loaded.\nCreate one to complete the MVC triad.")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #6c7086; font-size: 12px; font-weight: 500; line-height: 16px;")
        placeholder_layout.addWidget(self.placeholder_label)

        # Horizontal button row inside placeholder
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.create_btn = QPushButton(f"Create {self.title}")
        self.create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: #11111b;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #cdd6f4;
            }}
        """)
        self.create_btn.clicked.connect(lambda: self.create_clicked.emit(self.role))
        btn_layout.addWidget(self.create_btn)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #45475a;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 4px;
                padding: 5px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #585b70;
            }}
        """)
        self.browse_btn.clicked.connect(lambda: self.browse_clicked.emit(self.role))
        btn_layout.addWidget(self.browse_btn)

        placeholder_layout.addLayout(btn_layout)

        self.main_layout.addWidget(self.placeholder)
        self.placeholder.hide()

        # Connect combo signals to jump actions
        self.class_combo.currentIndexChanged.connect(self._on_class_selected)
        self.method_combo.currentIndexChanged.connect(self._on_method_selected)

    def set_file_path(self, path: str, exists: bool = True):
        """
        Updates the UI to reflect if a file is loaded for this pane.
        Hides the editor and shows the creation placeholder if file does not exist.
        """
        self.editor.current_file_path = path
        if path and exists:
            self.editor._run_live_lint()

        if not path:
            self.file_label.setText("No File Loaded")
            self.editor.hide()
            self.header.hide()
            self.placeholder.hide()
            return

        import os
        filename = os.path.basename(path)
        self.file_label.setText(filename)
        
        if exists:
            self.placeholder.hide()
            self.editor.show()
            self.header.show()
        else:
            self.editor.hide()
            self.header.hide()
            self.placeholder.show()
            self.placeholder_label.setText(f"Missing {self.title} counterpart:\n{filename}\n\nWould you like to create it?")

    def set_dirty(self, is_dirty: bool):
        text = self.file_label.text().replace(" *", "")
        if is_dirty:
            self.file_label.setText(text + " *")
            self.file_label.setStyleSheet("color: #f5e0dc; font-weight: bold; font-size: 11px;")
        else:
            self.file_label.setText(text)
            self.file_label.setStyleSheet("color: #a6adc8; font-weight: 500; font-size: 11px;")

    def update_outline(self, outline: dict):
        """
        Refreshes class and method dropdown breadcrumbs.
        """
        self._outline = outline or {'classes': [], 'functions': []}
        
        # Block signals temporarily to prevent triggering cursor jumps
        self.class_combo.blockSignals(True)
        self.method_combo.blockSignals(True)
        
        self.class_combo.clear()
        self.method_combo.clear()
        
        self.class_combo.addItem("[No Class]", None)
        for c in self._outline.get('classes', []):
            self.class_combo.addItem(c['name'], c)
            
        self.method_combo.addItem("[No Method]", None)
        # Populate all global functions
        for f in self._outline.get('functions', []):
            self.method_combo.addItem(f['name'], f)

        self.class_combo.blockSignals(False)
        self.method_combo.blockSignals(False)

    def set_active_method(self, class_name: str, method_name: str):
        """
        Updates dropdown indices based on editor's cursor line, without scrolling.
        """
        self.class_combo.blockSignals(True)
        self.method_combo.blockSignals(True)

        # 1. Update class selection
        found_class = False
        if class_name:
            for idx in range(self.class_combo.count()):
                if self.class_combo.itemText(idx) == class_name:
                    self.class_combo.setCurrentIndex(idx)
                    found_class = True
                    break
        if not found_class:
            self.class_combo.setCurrentIndex(0)

        # 2. Repopulate method combo box depending on class selection
        self.method_combo.clear()
        self.method_combo.addItem("[No Method]", None)
        
        active_class_data = self.class_combo.currentData()
        if active_class_data:
            # Add methods of this class
            for m in active_class_data.get('methods', []):
                self.method_combo.addItem(m['name'], m)
        else:
            # Add global functions
            for f in self._outline.get('functions', []):
                self.method_combo.addItem(f['name'], f)

        # 3. Update method selection
        found_method = False
        if method_name:
            for idx in range(self.method_combo.count()):
                if self.method_combo.itemText(idx) == method_name:
                    self.method_combo.setCurrentIndex(idx)
                    found_method = True
                    break
        if not found_method:
            self.method_combo.setCurrentIndex(0)

        self.class_combo.blockSignals(False)
        self.method_combo.blockSignals(False)

    def _on_class_selected(self, index):
        class_data = self.class_combo.itemData(index)
        
        # Populate methods
        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        self.method_combo.addItem("[No Method]", None)
        
        if class_data:
            for m in class_data.get('methods', []):
                self.method_combo.addItem(m['name'], m)
        else:
            for f in self._outline.get('functions', []):
                self.method_combo.addItem(f['name'], f)
        self.method_combo.blockSignals(False)

        # Scroll to class start
        if class_data:
            self.jump_to_line(class_data['start_line'])

    def _on_method_selected(self, index):
        method_data = self.method_combo.itemData(index)
        if method_data:
            self.jump_to_line(method_data['start_line'])

    def jump_to_line(self, line: int):
        """
        Scrolls the text editor to bring the specified line to view and set cursor there.
        """
        doc = self.editor.document()
        block = doc.findBlockByLineNumber(line - 1)
        if block.isValid():
            # Get role-specific highlight color
            colors = {
                'model': '#203d29',        # Soft green
                'view': '#3d253a',         # Soft pink/magenta
                'controller': '#1d2c40'    # Soft blue
            }
            color_hex = colors.get(self.role, '#3e302f')
            self.editor.highlight_target_line(line, color_hex)
            
            cursor = self.editor.textCursor()
            cursor.setPosition(block.position())
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            
            # Request connection highlights from Controller
            self.jump_to_line_requested.emit(line)

    def highlight_block_range(self, start_line: int, end_line: int):
        """
        Highlights the block's line range using role-specific color.
        """
        self.editor.block_start_line = start_line
        self.editor.block_end_line = end_line
        
        # Determine background block color based on role
        colors = {
            'model': QColor("#142218"),       # Soft dark green
            'view': QColor("#241623"),        # Soft dark pink
            'controller': QColor("#121b27")   # Soft dark blue
        }
        self.editor.block_highlight_color = colors.get(self.role, QColor("#1c1d30"))
        self.editor.highlight_current_line()

    def clear_block_highlight(self):
        """
        Clears the block highlight.
        """
        self.editor.block_start_line = None
        self.editor.block_end_line = None
        self.editor.highlight_current_line()
