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

try:
    import libcst as cst
    from libcst.metadata import PositionProvider, MetadataWrapper
except ImportError:
    cst = None
    PositionProvider = None
    MetadataWrapper = None

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

    def __init__(self, config=None):
        super().__init__()
        self.config = config
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
        self.connections_changed.emit([])

    # Set file content and parse its outline
    def set_content(self, role: str, content: str, mark_dirty: bool = True):
        if self._triad_contents[role] != content or self._triad_outlines[role] is None:
            self._triad_contents[role] = content
            self.content_changed.emit(role, content)
            
            # Update outline based on the new content
            self.parse_outline(role, content)
            
            if mark_dirty:
                self.set_dirty(role, True)
                
            # Re-analyze connections
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

        use_cst = True
        if self.config is not None:
            use_cst = getattr(self.config, 'use_cst', True)

        if use_cst and cst is not None:
            try:
                module = cst.parse_module(content)
                wrapper = MetadataWrapper(module)

                class OutlineCSTVisitor(cst.CSTVisitor):
                    METADATA_DEPENDENCIES = (PositionProvider,)

                    def __init__(self):
                        super().__init__()
                        self.classes = []
                        self.functions = []
                        self.signals = []
                        self.declarations = []
                        self.class_stack = []

                    def get_extended_range(self, node: cst.CSTNode):
                        pos = self.get_metadata(PositionProvider, node)
                        start_line = pos.start.line
                        end_line = pos.end.line

                        # Only include contiguous leading comments directly attached to this node
                        if node.leading_lines:
                            leading_comment_start = None
                            for ll in reversed(node.leading_lines):
                                if getattr(ll, "comment", None) is not None:
                                    lpos = self.get_metadata(PositionProvider, ll)
                                    leading_comment_start = lpos.start.line
                                else:
                                    # Hit a blank line: do not extend further upward
                                    break
                            if leading_comment_start is not None:
                                start_line = min(start_line, leading_comment_start)

                        # Only include contiguous footer comments directly inside this block
                        if hasattr(node, 'body') and isinstance(node.body, cst.IndentedBlock):
                            if node.body.footer:
                                footer_comment_end = None
                                for f in node.body.footer:
                                    if getattr(f, "comment", None) is not None:
                                        fpos = self.get_metadata(PositionProvider, f)
                                        footer_comment_end = fpos.end.line
                                    else:
                                        # Hit a blank line: do not extend further downward
                                        break
                                if footer_comment_end is not None:
                                    end_line = max(end_line, footer_comment_end)

                        return start_line, end_line

                    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
                        start_line, end_line = self.get_extended_range(node)
                        pos = self.get_metadata(PositionProvider, node)
                        class_info = {
                            'type': 'class',
                            'name': node.name.value,
                            'start_line': start_line,
                            'end_line': end_line,
                            'line': pos.start.line,
                            'methods': [],
                            'properties': [],
                            'signals': [],
                            'declarations': []
                        }
                        if not self.class_stack:
                            self.classes.append(class_info)
                        self.class_stack.append(class_info)
                        return True

                    def leave_ClassDef(self, node: cst.ClassDef) -> None:
                        self.class_stack.pop()

                    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
                        if len(self.class_stack) > 1:
                            return False

                        start_line, end_line = self.get_extended_range(node)
                        pos = self.get_metadata(PositionProvider, node)
                        args = [param.name.value for param in node.params.params if param.name.value != 'self']
                        sig = f"({', '.join(args)})"

                        is_property = False
                        for d in node.decorators:
                            dec_code = ""
                            if isinstance(d.decorator, cst.Name):
                                dec_code = d.decorator.value
                            elif isinstance(d.decorator, cst.Attribute):
                                if hasattr(d.decorator.value, 'value'):
                                    dec_code = f"{d.decorator.value.value}.{d.decorator.attr.value}"
                            if "property" in dec_code or "setter" in dec_code:
                                is_property = True

                        current_class = self.class_stack[-1]['name'] if self.class_stack else None
                        item_type = 'property' if is_property else ('method' if current_class else 'function')

                        item_info = {
                            'type': item_type,
                            'name': node.name.value,
                            'start_line': start_line,
                            'end_line': end_line,
                            'line': pos.start.line,
                            'args': args,
                            'signature': sig,
                            'class_name': current_class
                        }

                        if self.class_stack:
                            if is_property:
                                self.class_stack[-1]['properties'].append(item_info)
                            else:
                                self.class_stack[-1]['methods'].append(item_info)
                        else:
                            self.functions.append(item_info)

                        return False

                    def visit_Assign(self, node: cst.Assign) -> bool:
                        pos = self.get_metadata(PositionProvider, node)
                        current_class = self.class_stack[-1]['name'] if self.class_stack else None
                        val_str = ""
                        is_signal = False
                        if isinstance(node.value, cst.Call):
                            func_name = ""
                            if isinstance(node.value.func, cst.Name):
                                func_name = node.value.func.value
                            elif isinstance(node.value.func, cst.Attribute):
                                func_name = node.value.func.attr.value
                            if "Signal" in func_name or "pyqtSignal" in func_name:
                                is_signal = True
                                val_str = func_name

                        for target in node.targets:
                            if isinstance(target.target, cst.Name):
                                name = target.target.value
                                item = {
                                    'type': 'signal' if is_signal else 'declaration',
                                    'name': name,
                                    'line': pos.start.line,
                                    'start_line': pos.start.line,
                                    'end_line': pos.end.line,
                                    'class_name': current_class,
                                    'details': val_str
                                }
                                if is_signal:
                                    if self.class_stack:
                                        self.class_stack[-1]['signals'].append(item)
                                    else:
                                        self.signals.append(item)
                                else:
                                    if self.class_stack:
                                        self.class_stack[-1]['declarations'].append(item)
                                    else:
                                        self.declarations.append(item)
                        return False

                    def visit_AnnAssign(self, node: cst.AnnAssign) -> bool:
                        pos = self.get_metadata(PositionProvider, node)
                        current_class = self.class_stack[-1]['name'] if self.class_stack else None
                        if isinstance(node.target, cst.Name):
                            name = node.target.value
                            item = {
                                'type': 'declaration',
                                'name': name,
                                'line': pos.start.line,
                                'start_line': pos.start.line,
                                'end_line': pos.end.line,
                                'class_name': current_class,
                                'details': ""
                            }
                            if self.class_stack:
                                self.class_stack[-1]['declarations'].append(item)
                            else:
                                self.declarations.append(item)
                        return False

                visitor = OutlineCSTVisitor()
                wrapper.visit(visitor)

                outline = {
                    'classes': visitor.classes,
                    'functions': visitor.functions,
                    'signals': visitor.signals,
                    'declarations': visitor.declarations,
                    'is_cst': True
                }
                self._triad_outlines[role] = outline
                self.outline_changed.emit(role, outline)
                return True
            except Exception:
                # Fallback to AST on syntax or parser error
                pass

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Ignore syntax errors (e.g. user is mid-typing), keep the previous valid outline
            return False
        except Exception:
            return False

        classes = []
        functions = []
        signals = []
        declarations = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                c_start = getattr(node, 'lineno', 1)
                if node.decorator_list:
                    c_start = min(c_start, node.decorator_list[0].lineno)
                class_info = {
                    'type': 'class',
                    'name': node.name,
                    'start_line': c_start,
                    'end_line': getattr(node, 'end_lineno', node.lineno),
                    'line': node.lineno,
                    'methods': [],
                    'properties': [],
                    'signals': [],
                    'declarations': []
                }
                for subnode in node.body:
                    if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        f_start = subnode.lineno
                        if subnode.decorator_list:
                            f_start = min(f_start, subnode.decorator_list[0].lineno)
                        args = [arg.arg for arg in subnode.args.args if arg.arg != 'self']
                        sig = f"({', '.join(args)})"
                        is_property = any(
                            (isinstance(d, ast.Name) and "property" in d.id)
                            or (isinstance(d, ast.Attribute) and ("property" in d.attr or "setter" in d.attr))
                            for d in subnode.decorator_list
                        )
                        m_type = 'property' if is_property else 'method'
                        m_info = {
                            'type': m_type,
                            'name': subnode.name,
                            'start_line': f_start,
                            'end_line': getattr(subnode, 'end_lineno', subnode.lineno),
                            'line': subnode.lineno,
                            'args': args,
                            'signature': sig,
                            'class_name': node.name
                        }
                        if is_property:
                            class_info['properties'].append(m_info)
                        else:
                            class_info['methods'].append(m_info)
                    elif isinstance(subnode, ast.Assign):
                        is_sig = False
                        sig_name = ""
                        if isinstance(subnode.value, ast.Call):
                            if isinstance(subnode.value.func, ast.Name) and ("Signal" in subnode.value.func.id or "pyqtSignal" in subnode.value.func.id):
                                is_sig = True
                                sig_name = subnode.value.func.id
                            elif isinstance(subnode.value.func, ast.Attribute) and ("Signal" in subnode.value.func.attr or "pyqtSignal" in subnode.value.func.attr):
                                is_sig = True
                                sig_name = subnode.value.func.attr
                        for target in subnode.targets:
                            if isinstance(target, ast.Name):
                                item = {
                                    'type': 'signal' if is_sig else 'declaration',
                                    'name': target.id,
                                    'line': subnode.lineno,
                                    'start_line': subnode.lineno,
                                    'end_line': getattr(subnode, 'end_lineno', subnode.lineno),
                                    'class_name': node.name,
                                    'details': sig_name
                                }
                                if is_sig:
                                    class_info['signals'].append(item)
                                else:
                                    class_info['declarations'].append(item)
                    elif isinstance(subnode, ast.AnnAssign):
                        if isinstance(subnode.target, ast.Name):
                            class_info['declarations'].append({
                                'type': 'declaration',
                                'name': subnode.target.id,
                                'line': subnode.lineno,
                                'start_line': subnode.lineno,
                                'end_line': getattr(subnode, 'end_lineno', subnode.lineno),
                                'class_name': node.name,
                                'details': ""
                            })
                classes.append(class_info)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_start = node.lineno
                if node.decorator_list:
                    f_start = min(f_start, node.decorator_list[0].lineno)
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    'type': 'function',
                    'name': node.name,
                    'start_line': f_start,
                    'end_line': getattr(node, 'end_lineno', node.lineno),
                    'line': node.lineno,
                    'args': args,
                    'signature': f"({', '.join(args)})",
                    'class_name': None
                })

        outline = {
            'classes': classes,
            'functions': functions,
            'signals': signals,
            'declarations': declarations,
            'is_cst': False
        }
        self._triad_outlines[role] = outline
        self.outline_changed.emit(role, outline)
        return True

    def get_symbols_list(self, role: str) -> list[dict]:
        """
        Returns a flat list of symbol dictionaries for the given role,
        including classes, methods, properties, signals, and declarations.
        """
        outline = self._triad_outlines.get(role)
        if not outline:
            return []

        symbols = []
        for c in outline.get('classes', []):
            symbols.append({
                'type': 'class',
                'name': c['name'],
                'line': c.get('line', c['start_line']),
                'start_line': c['start_line'],
                'end_line': c['end_line'],
                'role': role,
                'class_name': None,
                'details': f"lines {c['start_line']}-{c['end_line']}"
            })
            for sig in c.get('signals', []):
                symbols.append({
                    'type': 'signal',
                    'name': sig['name'],
                    'line': sig['line'],
                    'start_line': sig.get('start_line', sig['line']),
                    'end_line': sig.get('end_line', sig['line']),
                    'role': role,
                    'class_name': c['name'],
                    'details': sig.get('details', '')
                })
            for decl in c.get('declarations', []):
                symbols.append({
                    'type': 'declaration',
                    'name': decl['name'],
                    'line': decl['line'],
                    'start_line': decl.get('start_line', decl['line']),
                    'end_line': decl.get('end_line', decl['line']),
                    'role': role,
                    'class_name': c['name'],
                    'details': decl.get('details', '')
                })
            for prop in c.get('properties', []):
                symbols.append({
                    'type': 'property',
                    'name': prop['name'],
                    'line': prop.get('line', prop['start_line']),
                    'start_line': prop['start_line'],
                    'end_line': prop['end_line'],
                    'role': role,
                    'class_name': c['name'],
                    'details': prop.get('signature', '')
                })
            for m in c.get('methods', []):
                symbols.append({
                    'type': 'method',
                    'name': m['name'],
                    'line': m.get('line', m['start_line']),
                    'start_line': m['start_line'],
                    'end_line': m['end_line'],
                    'role': role,
                    'class_name': c['name'],
                    'details': m.get('signature', '')
                })

        for f in outline.get('functions', []):
            symbols.append({
                'type': 'function',
                'name': f['name'],
                'line': f.get('line', f['start_line']),
                'start_line': f['start_line'],
                'end_line': f['end_line'],
                'role': role,
                'class_name': None,
                'details': f.get('signature', '')
            })

        for sig in outline.get('signals', []):
            symbols.append({
                'type': 'signal',
                'name': sig['name'],
                'line': sig['line'],
                'start_line': sig.get('start_line', sig['line']),
                'end_line': sig.get('end_line', sig['line']),
                'role': role,
                'class_name': None,
                'details': sig.get('details', '')
            })

        for decl in outline.get('declarations', []):
            symbols.append({
                'type': 'declaration',
                'name': decl['name'],
                'line': decl['line'],
                'start_line': decl.get('start_line', decl['line']),
                'end_line': decl.get('end_line', decl['line']),
                'role': role,
                'class_name': None,
                'details': decl.get('details', '')
            })

        return symbols

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

        for c in outline.get('classes', []):
            if c['start_line'] <= line <= c['end_line']:
                cls_name = c['name']
                for p in c.get('properties', []):
                    if p['start_line'] <= line <= p['end_line']:
                        method_name = p['name']
                        break
                if not method_name:
                    for m in c.get('methods', []):
                        if m['start_line'] <= line <= m['end_line']:
                            method_name = m['name']
                            break
                break

        if not cls_name:
            for f in outline.get('functions', []):
                if f['start_line'] <= line <= f['end_line']:
                    method_name = f['name']
                    break

        old_cls, old_method = self._triad_active_methods[role]
        if old_cls != cls_name or old_method != method_name:
            self._triad_active_methods[role] = (cls_name, method_name)
            self.active_method_changed.emit(role, cls_name or "", method_name or "")

    def get_active_block_range(self, role: str, line: int) -> tuple[int, int] | None:
        """
        Calculates the start and end lines of the class, method, property, or function
        containing the given line number.
        """
        outline = self._triad_outlines.get(role)
        if not outline:
            return None

        # Check classes first
        for c in outline.get('classes', []):
            if c['start_line'] <= line <= c['end_line']:
                # Check properties inside this class
                for p in c.get('properties', []):
                    if p['start_line'] <= line <= p['end_line']:
                        return p['start_line'], p['end_line']
                # Check methods inside this class
                for m in c.get('methods', []):
                    if m['start_line'] <= line <= m['end_line']:
                        return m['start_line'], m['end_line']
                # Check signals inside this class
                for s in c.get('signals', []):
                    if s['start_line'] <= line <= s['end_line']:
                        return s['start_line'], s['end_line']
                # Check declarations inside this class
                for d in c.get('declarations', []):
                    if d['start_line'] <= line <= d['end_line']:
                        return d['start_line'], d['end_line']

                # If inside class before first member, highlight class header and docstring
                members = c.get('methods', []) + c.get('properties', []) + c.get('signals', []) + c.get('declarations', [])
                if members:
                    first_member_start = min(item['start_line'] for item in members)
                    if line < first_member_start:
                        return c['start_line'], max(c['start_line'], first_member_start - 1)

                return c['start_line'], c['end_line']

        # Check global functions
        for f in outline.get('functions', []):
            if f['start_line'] <= line <= f['end_line']:
                return f['start_line'], f['end_line']

        return None

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
