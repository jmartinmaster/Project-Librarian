# app/views/editor.py - Editor Pane and Syntax Highlighter for MVC Sync Editor
# Copyright (C) 2026 Jamie Martin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QPlainTextEdit, QTextEdit
)
from PyQt6.QtGui import QPainter, QTextCharFormat, QColor, QFont, QSyntaxHighlighter, QTextFormat
from PyQt6.QtCore import QSize, Qt, QRect, QRegularExpression, pyqtSignal

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
                    "dict", "set", "tuple", "super", "self", "open", "Exception"]
        for word in builtins:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.highlighting_rules.append((pattern, builtin_format))

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


class PyCodeEditor(QPlainTextEdit):
    """
    Custom Code Editor widget incorporating Python Syntax Highlighting,
    line number painting, tab-to-spaces auto-handling, auto-indentation,
    and current line highlighting.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.target_line = None
        self.target_highlight_color = QColor("#3e302f")

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
        
        # 1. Subtle current line cursor highlight
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#1e1e2e"))  # Subtle active-line highlight
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
            
        # 2. Bright target line highlight
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
                
        self.setExtraSelections(extra_selections)

    def highlight_target_line(self, line: int, color_hex: str = "#3e302f"):
        self.target_line = line
        self.target_highlight_color = QColor(color_hex)
        self.highlight_current_line()

    def mousePressEvent(self, event):
        # Clear target line highlight on manual mouse clicks
        self.target_line = None
        self.highlight_current_line()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        # Clear target line highlight on manual typing
        self.target_line = None
        self.highlight_current_line()
        
        # Override Tab to insert 4 spaces
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText("    ")
            return

        # Override Enter for smart indentation
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            cursor = self.textCursor()
            current_block = cursor.block()
            text = current_block.text()
            
            # Extract spacing indent of current line
            indent = ""
            for char in text:
                if char.isspace():
                    indent += char
                else:
                    break
            
            # Check if ends with colon
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
            
            # Step over if matching close quote
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


class EditorPane(QWidget):
    """
    Self-contained panel wrapping the Python editor, file metadata header,
    breadcrumb navigators, and a placeholder screen for missing files.
    """
    jump_to_line_requested = pyqtSignal(int)
    create_clicked = pyqtSignal(str) # role
    browse_clicked = pyqtSignal(str) # role

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
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

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
        header_layout.addWidget(self.badge)

        # File path label
        self.file_label = QLabel("No File Loaded")
        self.file_label.setStyleSheet("color: #a6adc8; font-weight: 500; font-size: 11px;")
        header_layout.addWidget(self.file_label)
        header_layout.addStretch()

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

        header_layout.addWidget(self.class_combo)
        header_layout.addWidget(QLabel(">"))
        header_layout.addWidget(self.method_combo)

        self.main_layout.addWidget(self.header)

        # 2. Text Editor
        self.editor = PyCodeEditor()
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
