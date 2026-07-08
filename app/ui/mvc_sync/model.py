# app/models/model.py - Model implementation for MVC Sync Editor
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

from PyQt6.QtCore import QObject, pyqtSignal
import ast
import os

class DocumentModel(QObject):
    """
    Model representing the state of the MVC Editor.
    Tracks workspace path, active MVC file triad, content, dirty state,
    AST-parsed code structures, cursor locations, and cross-file method connections.
    """
    # Signals to notify the View / Controller of changes
    workspace_changed = pyqtSignal(str)              # Current folder path
    triad_changed = pyqtSignal(str, str, str)       # model_path, view_path, controller_path
    content_changed = pyqtSignal(str, str)          # role ('model'|'view'|'controller'), text content
    dirty_changed = pyqtSignal(str, bool)           # role, is_dirty
    outline_changed = pyqtSignal(str, dict)         # role, outline dictionary
    active_method_changed = pyqtSignal(str, str, str) # role, class_name, method_name
    connections_changed = pyqtSignal(list)          # list of detected connections/relations
    status_message_triggered = pyqtSignal(str)      # Message to display in status bar

    def __init__(self):
        super().__init__()
        self._workspace_path = None
        self._triad_paths = {'model': None, 'view': None, 'controller': None}
        self._triad_contents = {'model': "", 'view': "", 'controller': ""}
        self._triad_dirty = {'model': False, 'view': False, 'controller': False}
        self._triad_outlines = {'model': None, 'view': None, 'controller': None}
        self._triad_active_methods = {'model': (None, None), 'view': (None, None), 'controller': (None, None)}
        self._connections = []

    # Getters and Setters for Workspace Path
    @property
    def workspace_path(self) -> str:
        return self._workspace_path

    @workspace_path.setter
    def workspace_path(self, path: str):
        if self._workspace_path != path:
            self._workspace_path = path
            self.workspace_changed.emit(path if path else "")

    # Getters for Sibling Paths and Content
    def get_path(self, role: str) -> str:
        return self._triad_paths.get(role)

    def get_content(self, role: str) -> str:
        return self._triad_contents.get(role, "")

    def is_dirty(self, role: str) -> bool:
        return self._triad_dirty.get(role, False)

    def get_outline(self, role: str) -> dict:
        return self._triad_outlines.get(role)

    def get_active_method(self, role: str) -> tuple:
        return self._triad_active_methods.get(role, (None, None))

    @property
    def connections(self) -> list:
        return self._connections

    # Set Triad Paths
    def set_triad_paths(self, model_path: str, view_path: str, controller_path: str):
        self._triad_paths['model'] = model_path
        self._triad_paths['view'] = view_path
        self._triad_paths['controller'] = controller_path
        
        # Reset contents, dirty state, outlines, active methods
        for role in ['model', 'view', 'controller']:
            self._triad_contents[role] = ""
            self._triad_dirty[role] = False
            self._triad_outlines[role] = None
            self._triad_active_methods[role] = (None, None)
        self._connections = []
        
        self.triad_changed.emit(
            model_path if model_path else "",
            view_path if view_path else "",
            controller_path if controller_path else ""
        )

    # Set file content and parse its outline
    def set_content(self, role: str, content: str, mark_dirty: bool = True):
        if self._triad_contents[role] != content:
            self._triad_contents[role] = content
            self.content_changed.emit(role, content)
            
            # Update outline based on the new content
            self.parse_outline(role, content)
            
            if mark_dirty:
                self.set_dirty(role, True)
                
            # If controller code changed, re-analyze connections
            if role == 'controller' or role == 'view':
                self.update_connections()

    def set_dirty(self, role: str, is_dirty: bool):
        if self._triad_dirty[role] != is_dirty:
            self._triad_dirty[role] = is_dirty
            self.dirty_changed.emit(role, is_dirty)

    def parse_outline(self, role: str, content: str) -> bool:
        """
        Parses python content and extracts classes and functions with line numbers.
        Saves result to outlines and emits outline_changed signal.
        """
        if not content:
            self._triad_outlines[role] = None
            self.outline_changed.emit(role, {})
            return True

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Ignore syntax errors (e.g. user is mid-typing), keep the previous valid outline
            return False
        except Exception:
            return False

        classes = []
        functions = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = []
                for subnode in node.body:
                    if isinstance(subnode, ast.FunctionDef):
                        methods.append({
                            'name': subnode.name,
                            'start_line': subnode.lineno,
                            'end_line': getattr(subnode, 'end_lineno', subnode.lineno),
                            'args': [arg.arg for arg in subnode.args.args if arg.arg != 'self']
                        })
                classes.append({
                    'name': node.name,
                    'start_line': node.lineno,
                    'end_line': getattr(node, 'end_lineno', node.lineno),
                    'methods': methods
                })
            elif isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'start_line': node.lineno,
                    'end_line': getattr(node, 'end_lineno', node.lineno),
                    'args': [arg.arg for arg in node.args.args]
                })

        outline = {'classes': classes, 'functions': functions}
        self._triad_outlines[role] = outline
        self.outline_changed.emit(role, outline)
        return True

    def update_active_location(self, role: str, line: int):
        """
        Calculates which class/method corresponds to the line number,
        updates state, and emits active_method_changed signal.
        """
        outline = self._triad_outlines[role]
        if not outline:
            return

        cls_name = None
        method_name = None

        # Check classes first
        for c in outline['classes']:
            if c['start_line'] <= line <= c['end_line']:
                cls_name = c['name']
                for m in c['methods']:
                    if m['start_line'] <= line <= m['end_line']:
                        method_name = m['name']
                        break
                break

        # Check global functions if not inside a class
        if not cls_name:
            for f in outline['functions']:
                if f['start_line'] <= line <= f['end_line']:
                    method_name = f['name']
                    break

        old_cls, old_method = self._triad_active_methods[role]
        if old_cls != cls_name or old_method != method_name:
            self._triad_active_methods[role] = (cls_name, method_name)
            self.active_method_changed.emit(role, cls_name or "", method_name or "")

    def update_connections(self):
        """
        Analyzes the controller and view code to identify signal connections 
        and cross-references (method calls or attribute updates).
        """
        controller_content = self._triad_contents['controller']
        if not controller_content:
            self._connections = []
            self.connections_changed.emit([])
            return

        try:
            tree = ast.parse(controller_content)
        except Exception:
            # syntax error during typing - keep the previous connections
            return

        connections = []

        # 1. Parse signal connections (e.g. self.view.open_triggered.connect(self.open_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'connect':
                    target_attr = node.func.value
                    if isinstance(target_attr, ast.Attribute):
                        obj = target_attr.value
                        if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name) and obj.value.id == 'self':
                            sender_type = obj.attr  # 'view' or 'model'
                            signal_name = target_attr.attr
                            if len(node.args) == 1 and isinstance(node.args[0], ast.Attribute):
                                arg_obj = node.args[0].value
                                if isinstance(arg_obj, ast.Name) and arg_obj.id == 'self':
                                    handler_name = node.args[0].attr
                                    connections.append({
                                        'source_role': sender_type,
                                        'source_element': signal_name,
                                        'type': 'signal_connect',
                                        'target_role': 'controller',
                                        'target_element': handler_name,
                                        'line': node.lineno
                                    })

        # 2. Parse method bodies to find references to self.view.method() or self.model.property
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for subnode in node.body:
                    if isinstance(subnode, ast.FunctionDef):
                        method_name = subnode.name
                        for inner in ast.walk(subnode):
                            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                                obj = inner.func.value
                                if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name) and obj.value.id == 'self':
                                    if obj.attr in ('view', 'model'):
                                        connections.append({
                                            'source_role': 'controller',
                                            'source_element': method_name,
                                            'type': 'method_call',
                                            'target_role': obj.attr,
                                            'target_element': inner.func.attr,
                                            'line': inner.lineno
                                        })
                            elif isinstance(inner, ast.Attribute):
                                obj = inner.value
                                if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name) and obj.value.id == 'self':
                                    if obj.attr in ('view', 'model'):
                                        connections.append({
                                            'source_role': 'controller',
                                            'source_element': method_name,
                                            'type': 'property_access',
                                            'target_role': obj.attr,
                                            'target_element': inner.attr,
                                            'line': inner.lineno
                                        })

        # Deduplicate signals/calls
        unique_connections = []
        seen = set()
        for conn in connections:
            key = (conn['source_role'], conn['source_element'], conn['target_role'], conn['target_element'], conn['type'])
            if key not in seen:
                seen.add(key)
                unique_connections.append(conn)

        self._connections = unique_connections
        self.connections_changed.emit(unique_connections)

    def trigger_status_message(self, message: str):
        self.status_message_triggered.emit(message)
