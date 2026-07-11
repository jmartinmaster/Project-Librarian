# app/controllers/controller.py - Controller implementation for MVC Sync Editor
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

from PyQt6.QtCore import QObject, QProcess, QDir, pyqtSignal, QThread
from PyQt6.QtWidgets import QFileDialog
import os
import ast

from app.views.mvc_sync.worker import ASTChunkerWorker

class EditorController(QObject):
    """
    Controller connecting the DocumentModel and EditorView.
    Coordinates file operations, updates AST mappings, synchronizes navigations,
    and runs subprocess execution for the user's project.
    """
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        
        self._sync_nav = True
        self._is_loading = False # Flag to ignore text changes during file loads
        
        # Subprocess runner state
        self.process = None
        
        # Connect model signals to view slots
        self.model.workspace_changed.connect(self.view.load_workspace)
        self.model.triad_changed.connect(self.handle_triad_changed)
        self.model.content_changed.connect(self.handle_model_content_changed)
        self.model.dirty_changed.connect(self.handle_model_dirty_changed)
        self.model.outline_changed.connect(self.handle_model_outline_changed)
        self.model.active_method_changed.connect(self.handle_model_active_method_changed)
        self.model.connections_changed.connect(self.view.populate_connections)
        self.model.status_message_triggered.connect(self.view.show_status)

        # Connect view signals to controller actions
        self.view.open_folder_triggered.connect(self.open_workspace)
        self.view.save_all_triggered.connect(self.save_all_files)
        self.view.run_triggered.connect(self.run_application)
        self.view.stop_triggered.connect(self.stop_application)
        self.view.file_selected.connect(self.open_file)
        self.view.connection_double_clicked.connect(self.navigate_to_connection)
        self.view.create_sibling_requested.connect(self.create_sibling_file)
        self.view.create_triad_requested.connect(self.create_new_mvc_triad)
        self.view.browse_sibling_requested.connect(self.browse_sibling_file)
        self.view.sync_nav_toggled.connect(self.set_sync_nav)
        self.view.about_triggered.connect(self.show_about_dialog)

        # Track cursor and text edits in editors
        self.view.model_pane.editor.cursorPositionChanged.connect(lambda: self.track_cursor('model'))
        self.view.view_pane.editor.cursorPositionChanged.connect(lambda: self.track_cursor('view'))
        self.view.controller_pane.editor.cursorPositionChanged.connect(lambda: self.track_cursor('controller'))

        self.view.model_pane.editor.textChanged.connect(lambda: self.update_model_content('model'))
        self.view.view_pane.editor.textChanged.connect(lambda: self.update_model_content('view'))
        self.view.controller_pane.editor.textChanged.connect(lambda: self.update_model_content('controller'))

        # Open the current directory as the default workspace
        initial_workspace = os.path.abspath(".")
        self.model.workspace_path = initial_workspace

    def on_editor_lost_focus(self, raw_text: str):
        """
        Triggered when clicking away from the editor area.
        Initiates a thread-safe background parse using ASTChunkerWorker.
        """
        self.chunker_thread = QThread()
        self.chunker_worker = ASTChunkerWorker(raw_text)
        
        self.chunker_worker.moveToThread(self.chunker_thread)
        
        # Connect thread start to worker process
        self.chunker_thread.started.connect(self.chunker_worker.process_text)
        
        # Connect worker results to corpus update (assuming self.update_corpus exists or will be implemented)
        if hasattr(self, 'update_corpus'):
            self.chunker_worker.chunks_ready.connect(self.update_corpus)
            
        # Clean up worker and thread safely
        self.chunker_worker.finished.connect(self.chunker_thread.quit)
        self.chunker_worker.finished.connect(self.chunker_worker.deleteLater)
        self.chunker_thread.finished.connect(self.chunker_thread.deleteLater)
        
        self.chunker_thread.start()

    # Workspace Folder I/O
    def open_workspace(self):
        dir_path = QFileDialog.getExistingDirectory(self.view, "Select Project Folder", self.model.workspace_path or "")
        if dir_path:
            self.model.workspace_path = dir_path

    # File loading operations
    def open_file(self, path: str):
        """
        Determines if a file is part of an MVC layout and loads either the triad or a single file.
        """
        if not path or not os.path.exists(path):
            return

        m_path, v_path, c_path = self.find_mvc_triad(path)
        
        self._is_loading = True
        
        # Show all columns for MVC mode
        self.view.model_pane.show()
        self.view.view_pane.show()
        self.view.controller_pane.show()
        
        # Reset badges to MVC roles
        self.view.model_pane.badge.setText("MODEL")
        self.view.model_pane.badge.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 4px; padding: 2px 6px;")
        self.view.view_pane.badge.setText("VIEW")
        self.view.view_pane.badge.setStyleSheet("background-color: #f5c2e7; color: #11111b; font-weight: bold; border-radius: 4px; padding: 2px 6px;")
        self.view.controller_pane.badge.setText("CONTROLLER")
        self.view.controller_pane.badge.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 4px; padding: 2px 6px;")

        if not (m_path or v_path or c_path):
            c_path = path

        # Load each file in the triad
        self.model.set_triad_paths(m_path or "", v_path or "", c_path or "")
        
        for role, filepath in [('model', m_path), ('view', v_path), ('controller', c_path)]:
            pane = getattr(self.view, f"{role}_pane")
            if filepath and os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    pane.set_file_path(filepath, exists=True)
                    pane.editor.setPlainText(content)
                    self.model.set_content(role, content, mark_dirty=False)
                except Exception as e:
                    self.model.trigger_status_message(f"Error loading {role}: {str(e)}")
            else:
                pane.set_file_path(filepath or "", exists=False)
                pane.editor.clear()
        
        self.model.trigger_status_message("Loaded MVC layout successfully.")
                
        self._is_loading = False
        
        # Initial connections update
        self.model.update_connections()
        
        # Update Workspace Dashboard
        self.update_view_dashboard()

    def find_mvc_triad(self, path: str):
        """
        Calculates MVC sibling paths using imports inside the file (if it's an entry point),
        or sibling folders/suffixes if it's one of the MVC files.
        """
        path = os.path.abspath(path)
        dirname = os.path.dirname(path)
        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        
        if ext != '.py':
            return None, None, None

        # Check if this is an entry point file (like main.py) and resolve from its imports
        m_path, v_path, c_path = self.find_triad_from_imports(path)
        if m_path or v_path or c_path:
            lower_filename = os.path.basename(path).lower()
            if "model" in lower_filename:
                m_path = path
            elif "view" in lower_filename:
                v_path = path
            elif "controller" in lower_filename:
                c_path = path
            return m_path, v_path, c_path

        parent_folder = os.path.basename(dirname).lower()
        model_path = None
        view_path = None
        controller_path = None

        # Rule 1: Sibling directories (models, views, controllers)
        if parent_folder in ('models', 'model', 'views', 'view', 'controllers', 'controller'):
            grand_parent = os.path.dirname(dirname)
            
            # Retrieve subfolders
            siblings = os.listdir(grand_parent)
            models_dir, views_dir, controllers_dir = None, None, None
            for sib in siblings:
                sib_path = os.path.join(grand_parent, sib)
                if os.path.isdir(sib_path):
                    name_low = sib.lower()
                    if name_low in ('models', 'model'):
                        models_dir = sib_path
                    elif name_low in ('views', 'view'):
                        views_dir = sib_path
                    elif name_low in ('controllers', 'controller'):
                        controllers_dir = sib_path

            # Deduce base name (e.g. strip suffixes like _model, _view, _controller)
            core_name = name
            for suffix in ('_model', '_view', '_controller', 'model', 'view', 'controller'):
                if core_name.lower().endswith(suffix):
                    core_name = core_name[:-len(suffix)]
                    if core_name.endswith('_'):
                        core_name = core_name[:-1]
                    break

            # Options for sibling files
            possible_models = [f"{core_name}_model.py", f"{core_name}model.py", f"{core_name}.py", "model.py"]
            possible_views = [f"{core_name}_view.py", f"{core_name}view.py", f"{core_name}.py", "view.py"]
            possible_controllers = [f"{core_name}_controller.py", f"{core_name}controller.py", f"{core_name}.py", "controller.py"]

            def get_sibling_path(folder, options):
                if not folder or not os.path.exists(folder):
                    return None
                for opt in options:
                    p = os.path.join(folder, opt)
                    if os.path.exists(p):
                        return p
                # Default path returning first option
                return os.path.join(folder, options[0])

            model_path = get_sibling_path(models_dir, possible_models)
            view_path = get_sibling_path(views_dir, possible_views)
            controller_path = get_sibling_path(controllers_dir, possible_controllers)

        # Rule 2: Suffixes in the same directory
        if not (model_path or view_path or controller_path):
            core_name = name
            is_suffix = False
            for suffix in ('_model', '_view', '_controller'):
                if name.lower().endswith(suffix):
                    core_name = name[:-len(suffix)]
                    is_suffix = True
                    break
            if is_suffix:
                model_path = os.path.join(dirname, f"{core_name}_model.py")
                view_path = os.path.join(dirname, f"{core_name}_view.py")
                controller_path = os.path.join(dirname, f"{core_name}_controller.py")

        # Ensure the opened file itself is always mapped to its corresponding role in the triad
        lower_filename = os.path.basename(path).lower()
        if "model" in lower_filename:
            model_path = path
        elif "view" in lower_filename:
            view_path = path
        elif "controller" in lower_filename:
            controller_path = path

        return model_path, view_path, controller_path

    def find_triad_from_imports(self, path: str):
        """
        Parses a python file to extract imports and maps them to model, view, and controller paths.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
        except Exception:
            return None, None, None

        imported_modules = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append((node.module, [n.name for n in node.names]))
            elif isinstance(node, ast.Import):
                for n in node.names:
                    imported_modules.append((n.name, []))

        workspace = self.model.workspace_path or os.path.dirname(path)
        m_path, v_path, c_path = None, None, None

        for mod_name, names in imported_modules:
            parts = mod_name.split('.')
            relative_file = os.path.join(*parts) + ".py"
            
            # Check relative to workspace, then relative to source dir
            full_path = os.path.join(workspace, relative_file)
            if not os.path.exists(full_path):
                full_path = os.path.join(os.path.dirname(path), relative_file)
                
            # Check package init
            if not os.path.exists(full_path):
                relative_init = os.path.join(*parts, "__init__.py")
                full_init = os.path.join(workspace, relative_init)
                if os.path.exists(full_init):
                    full_path = full_init
                else:
                    full_init = os.path.join(os.path.dirname(path), relative_init)
                    if os.path.exists(full_init):
                        full_path = full_init

            if os.path.exists(full_path):
                path_lower = full_path.lower()
                is_model = 'model' in path_lower or any('model' in n.lower() for n in names)
                is_view = 'view' in path_lower or any('view' in n.lower() for n in names)
                is_controller = 'controller' in path_lower or any('controller' in n.lower() for n in names)

                if is_model:
                    m_path = full_path
                elif is_view:
                    v_path = full_path
                elif is_controller:
                    c_path = full_path

        return m_path, v_path, c_path

    # Lazy Sibling Creation
    def create_sibling_file(self, role: str, template_ref: str):
        """
        Creates a new MVC file at the expected sibling path and fills it with boilerplate code.
        """
        target_path = self.model.get_path(role)
        if not target_path:
            return
            
        # Boilerplate code templates
        templates = {
            'model': (
                "from PyQt6.QtCore import QObject, pyqtSignal\n\n"
                "class DocumentModel(QObject):\n"
                "    \"\"\"\n"
                "    Standard MVC Model representation.\n"
                "    \"\"\"\n"
                "    text_changed = pyqtSignal(str)\n"
                "    file_path_changed = pyqtSignal(str)\n\n"
                "    def __init__(self):\n"
                "        super().__init__()\n"
                "        self._text_content = \"\"\n"
                "        self._file_path = None\n\n"
                "    @property\n"
                "    def text_content(self) -> str:\n"
                "        return self._text_content\n\n"
                "    @text_content.setter\n"
                "    def text_content(self, text: str):\n"
                "        if self._text_content != text:\n"
                "            self._text_content = text\n"
                "            self.text_changed.emit(text)\n"
            ),
            'view': (
                "from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel\n"
                "from PyQt6.QtCore import pyqtSignal\n\n"
                "class EditorView(QMainWindow):\n"
                "    \"\"\"\n"
                "    Standard MVC View representing the GUI window.\n"
                "    \"\"\"\n"
                "    open_triggered = pyqtSignal()\n"
                "    save_triggered = pyqtSignal(str)\n"
                "    text_user_edited = pyqtSignal(str)\n\n"
                "    def __init__(self):\n"
                "        super().__init__()\n"
                "        self.setWindowTitle(\"MVC Layout View\")\n"
                "        self.resize(600, 450)\n"
                "        self.init_ui()\n\n"
                "    def init_ui(self):\n"
                "        self.central_widget = QWidget()\n"
                "        self.setCentralWidget(self.central_widget)\n"
                "        layout = QVBoxLayout(self.central_widget)\n"
                "        \n"
                "        self.label = QLabel(\"Welcome to the MVC App View\")\n"
                "        layout.addWidget(self.label)\n"
                "        \n"
                "        self.open_btn = QPushButton(\"Open File\")\n"
                "        self.open_btn.clicked.connect(self.open_triggered.emit)\n"
                "        layout.addWidget(self.open_btn)\n\n"
                "    def set_content(self, text: str):\n"
                "        self.label.setText(text)\n\n"
                "    def set_file_path(self, path: str):\n"
                "        self.setWindowTitle(f\"MVC Layout View - {path}\")\n"
            ),
            'controller': (
                "class EditorController:\n"
                "    \"\"\"\n"
                "    Standard MVC Controller tying together Model and View.\n"
                "    \"\"\"\n"
                "    def __init__(self, model, view):\n"
                "        self.model = model\n"
                "        self.view = view\n\n"
                "        # Connect signals\n"
                "        self.model.text_changed.connect(self.view.set_content)\n"
                "        self.model.file_path_changed.connect(self.view.set_file_path)\n"
                "        self.view.open_triggered.connect(self.open_file)\n\n"
                "    def open_file(self):\n"
                "        pass\n"
            )
        }
        
        content = templates.get(role, "# Custom MVC File\n")
        try:
            # Ensure target parent folders exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.model.trigger_status_message(f"Created missing MVC file: {os.path.basename(target_path)}")
            # Reload triad to pull in new sibling
            active_paths = [self.model.get_path('model'), self.model.get_path('view'), self.model.get_path('controller')]
            non_empty_paths = [p for p in active_paths if p]
            if non_empty_paths:
                self.open_file(non_empty_paths[0])
        except Exception as e:
            self.model.trigger_status_message(f"Error creating sibling: {str(e)}")

    def create_new_mvc_triad(self, base_name: str, target_dir: str):
        """
        Creates an entire new MVC triad (Model, View, Controller) in one click
        with pre-wired boilerplate templates.
        """
        import re
        import os

        # Convert CamelCase/space-separated name to snake_case and CamelCase
        snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', base_name).lower().replace(" ", "_")
        snake_name = re.sub(r'_+', '_', snake_name)
        camel_name = "".join(part.capitalize() for part in snake_name.split("_"))

        workspace_path = self.model.workspace_path or target_dir or os.path.abspath(".")
        
        models_dir = os.path.join(workspace_path, "models")
        views_dir = os.path.join(workspace_path, "views")
        controllers_dir = os.path.join(workspace_path, "controllers")

        try:
            os.makedirs(models_dir, exist_ok=True)
            os.makedirs(views_dir, exist_ok=True)
            os.makedirs(controllers_dir, exist_ok=True)

            m_path = os.path.join(models_dir, f"{snake_name}_model.py")
            v_path = os.path.join(views_dir, f"{snake_name}_view.py")
            c_path = os.path.join(controllers_dir, f"{snake_name}_controller.py")

            model_content = (
                "from PyQt6.QtCore import QObject, pyqtSignal\n\n"
                f"class {camel_name}Model(QObject):\n"
                "    \"\"\"\n"
                f"    Model representing data and business logic for {camel_name}.\n"
                "    \"\"\"\n"
                "    data_changed = pyqtSignal(str)\n\n"
                "    def __init__(self) -> None:\n"
                "        super().__init__()\n"
                f"        self._data = \"Initial data for {camel_name}\"\n\n"
                "    @property\n"
                "    def data(self) -> str:\n"
                "        return self._data\n\n"
                "    @data.setter\n"
                "    def data(self, value: str) -> None:\n"
                "        if self._data != value:\n"
                "            self._data = value\n"
                "            self.data_changed.emit(value)\n"
            )

            view_content = (
                "from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel\n"
                "from PyQt6.QtCore import pyqtSignal\n\n"
                f"class {camel_name}View(QWidget):\n"
                "    \"\"\"\n"
                f"    View representing the GUI layout for {camel_name}.\n"
                "    \"\"\"\n"
                "    action_triggered = pyqtSignal()\n\n"
                "    def __init__(self, parent: QWidget | None = None) -> None:\n"
                "        super().__init__(parent)\n"
                "        self.init_ui()\n\n"
                "    def init_ui(self) -> None:\n"
                "        layout = QVBoxLayout(self)\n"
                f"        self.label = QLabel(\"Active view: {camel_name}\", self)\n"
                "        self.button = QPushButton(\"Trigger Action\", self)\n"
                "        self.button.clicked.connect(self.action_triggered.emit)\n"
                "        layout.addWidget(self.label)\n"
                "        layout.addWidget(self.button)\n\n"
                "    def update_display(self, text: str) -> None:\n"
                "        self.label.setText(text)\n"
            )

            controller_content = (
                f"from models.{snake_name}_model import {camel_name}Model\n"
                f"from views.{snake_name}_view import {camel_name}View\n\n"
                f"class {camel_name}Controller:\n"
                "    \"\"\"\n"
                f"    Controller linking {camel_name}Model and {camel_name}View.\n"
                "    \"\"\"\n"
                f"    def __init__(self, model: {camel_name}Model, view: {camel_name}View) -> None:\n"
                "        self.model = model\n"
                "        self.view = view\n"
                "        \n"
                "        # Wire model signals to view slots\n"
                "        self.model.data_changed.connect(self.view.update_display)\n"
                "        \n"
                "        # Wire view signals to controller slots\n"
                "        self.view.action_triggered.connect(self.handle_action)\n\n"
                "    def handle_action(self) -> None:\n"
                f"        self.model.data = \"Action triggered in {camel_name}Controller!\"\n"
            )

            with open(m_path, "w", encoding="utf-8") as f:
                f.write(model_content)
            with open(v_path, "w", encoding="utf-8") as f:
                f.write(view_content)
            with open(c_path, "w", encoding="utf-8") as f:
                f.write(controller_content)

            self.model.trigger_status_message(f"Created new MVC triad: {camel_name}")
            self.open_file(c_path)
        except Exception as e:
            self.model.trigger_status_message(f"Error creating MVC triad: {str(e)}")

    def browse_sibling_file(self, role: str):
        """
        Allows the user to manually select a Python file to associate as the sibling for the given MVC role.
        """
        start_dir = self.model.workspace_path or ""
        active_paths = [self.model.get_path('model'), self.model.get_path('view'), self.model.get_path('controller')]
        valid_paths = [p for p in active_paths if p and os.path.exists(p)]
        if valid_paths:
            start_dir = os.path.dirname(valid_paths[0])
            
        file_path, _ = QFileDialog.getOpenFileName(
            self.view, f"Select Python File for {role.upper()}", 
            start_dir, "Python Files (*.py);;All Files (*)"
        )
        if file_path:
            self._is_loading = True
            self.model._triad_paths[role] = file_path
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                pane = getattr(self.view, f"{role}_pane")
                pane.set_file_path(file_path, exists=True)
                pane.editor.setPlainText(content)
                self.model.set_content(role, content, mark_dirty=False)
                self.model.trigger_status_message(f"Associated {role} with: {os.path.basename(file_path)}")
                self.model.update_connections()
                self.update_view_dashboard()
            except Exception as e:
                self.model.trigger_status_message(f"Error loading associated file: {str(e)}")
                
            self._is_loading = False

    def update_view_dashboard(self):
        """
        Updates the status dashboard in the Workspace Tab.
        """
        model_path = self.model.get_path('model')
        view_path = self.model.get_path('view')
        controller_path = self.model.get_path('controller')
        
        for role, path in [('model', model_path), ('view', view_path), ('controller', controller_path)]:
            exists = os.path.exists(path) if path else False
            self.view.set_dashboard_role_status(role, path or "", exists)

    # Text Syncing & Dirty State Management
    def update_model_content(self, role: str):
        """
        Pushes editor edits to the Model, triggers background outline/connection updates.
        """
        if self._is_loading:
            return
        pane = getattr(self.view, f"{role}_pane")
        text = pane.editor.toPlainText()
        self.model.set_content(role, text, mark_dirty=True)

    def save_all_files(self):
        """
        Saves all modified open documents.
        """
        saved_count = 0
        for role in ['model', 'view', 'controller']:
            filepath = self.model.get_path(role)
            if filepath and self.model.is_dirty(role):
                try:
                    content = self.model.get_content(role)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.model.set_dirty(role, False)
                    saved_count += 1
                except Exception as e:
                    self.model.trigger_status_message(f"Error saving {role}: {str(e)}")
                    return
        
        if saved_count > 0:
            self.model.trigger_status_message(f"Saved {saved_count} file(s) successfully.")
        else:
            self.model.trigger_status_message("All files are up to date.")

    # Model signal handlers
    def handle_triad_changed(self, m_path, v_path, c_path):
        pass

    def handle_model_content_changed(self, role: str, content: str):
        # We handle edits in the GUI, but if text changes externally, we set it
        pass

    def handle_model_dirty_changed(self, role: str, is_dirty: bool):
        pane = getattr(self.view, f"{role}_pane")
        pane.set_dirty(is_dirty)

    def handle_model_outline_changed(self, role: str, outline: dict):
        pane = getattr(self.view, f"{role}_pane")
        pane.update_outline(outline)

    def handle_model_active_method_changed(self, role: str, class_name: str, method_name: str):
        pane = getattr(self.view, f"{role}_pane")
        pane.set_active_method(class_name, method_name)

    # Sync navigation & Connection handlers
    def set_sync_nav(self, enabled: bool):
        self._sync_nav = enabled

    def track_cursor(self, role: str):
        """
        Fires on cursor movement to check lines, triggers sibling sync if cursor is in Controller.
        """
        if self._is_loading:
            return
        pane = getattr(self.view, f"{role}_pane")
        cursor = pane.editor.textCursor()
        line = cursor.blockNumber() + 1
        self.model.update_active_location(role, line)
        
        # Perform sync scrolling from Controller -> Model/View
        if role == 'controller' and self._sync_nav:
            _, method_name = self.model.get_active_method('controller')
            if method_name:
                self.sync_siblings_to_controller_method(method_name)

    def sync_siblings_to_controller_method(self, method_name: str):
        conns = self.model.connections
        view_target = None
        model_target = None
        
        for conn in conns:
            # If the focused method in controller has calls to view/model
            if conn['source_role'] == 'controller' and conn['source_element'] == method_name:
                if conn['target_role'] == 'view' and not view_target:
                    view_target = conn['target_element']
                elif conn['target_role'] == 'model' and not model_target:
                    model_target = conn['target_element']
            # If a View signal connects to this Controller method
            elif conn['target_role'] == 'controller' and conn['target_element'] == method_name:
                if conn['source_role'] == 'view' and not view_target:
                    view_target = conn['source_element']
                elif conn['source_role'] == 'model' and not model_target:
                    model_target = conn['source_element']

        if view_target:
            self.scroll_pane_to_element('view', view_target)
        if model_target:
            self.scroll_pane_to_element('model', model_target)

    def scroll_pane_to_element(self, role: str, name: str):
        outline = self.model.get_outline(role)
        if not outline:
            return
            
        start_line = None
        
        # Search class methods
        for c in outline.get('classes', []):
            if c['name'] == name:
                start_line = c['start_line']
                break
            for m in c['methods']:
                if m['name'] == name:
                    start_line = m['start_line']
                    break
            if start_line:
                break
                
        # Search global functions
        if not start_line:
            for f in outline.get('functions', []):
                if f['name'] == name:
                    start_line = f['start_line']
                    break
                    
        if start_line:
            pane = getattr(self.view, f"{role}_pane")
            # Temporarily block signals to avoid feedback scroll triggers
            pane.editor.blockSignals(True)
            pane.jump_to_line(start_line)
            pane.editor.blockSignals(False)

    def navigate_to_connection(self, conn: dict):
        """
        Handles double-click in MVC Inspector to jump editors to respective connection lines.
        """
        # Jump in Controller (source of method_call / property_access) or Target of signal connections
        controller_pane = self.view.controller_pane
        controller_line = conn.get('line')
        
        if controller_line:
            controller_pane.jump_to_line(controller_line)
            
        # Jump in sibling pane
        sibling_role = conn['source_role'] if conn['target_role'] == 'controller' else conn['target_role']
        sibling_element = conn['source_element'] if conn['target_role'] == 'controller' else conn['target_element']
        
        self.scroll_pane_to_element(sibling_role, sibling_element)

    # Subprocess run console execution
    def run_application(self):
        """
        Launches the project entry point (main.py in workspace root) inside a background subprocess.
        """
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.model.trigger_status_message("Application is already running.")
            return

        workspace = self.model.workspace_path
        if not workspace:
            self.model.trigger_status_message("Select a workspace directory first.")
            return
            
        # Check standard entry point filenames
        entrypoint = os.path.join(workspace, "main.py")
        if not os.path.exists(entrypoint):
            entrypoint = os.path.join(workspace, "run.py")
            if not os.path.exists(entrypoint):
                # Fallback to controller path itself
                entrypoint = self.model.get_path('controller')
                if not entrypoint or not os.path.exists(entrypoint):
                    self.model.trigger_status_message("No executable entry point (main.py) found.")
                    return

        # Prepare QProcess
        self.process = QProcess()
        self.process.setWorkingDirectory(workspace)
        
        # Redirect outputs
        self.process.readyReadStandardOutput.connect(self.read_process_stdout)
        self.process.readyReadStandardError.connect(self.read_process_stderr)
        self.process.finished.connect(self.handle_process_finished)

        # Clear UI logs and set buttons
        self.view.clear_console()
        self.view.append_console_text(f"--- Starting execution of: {os.path.basename(entrypoint)} ---\n")
        self.view.set_running_state(True)
        
        # Start command
        self.process.start("python", [entrypoint])
        if not self.process.waitForStarted(1500):
            self.view.append_console_text("Failed to start python process. Check your python path.\n", is_error=True)
            self.view.set_running_state(False)

    def read_process_stdout(self):
        data = self.process.readAllStandardOutput().data()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin1")
        self.view.append_console_text(text, is_error=False)

    def read_process_stderr(self):
        data = self.process.readAllStandardError().data()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin1")
        self.view.append_console_text(text, is_error=True)

    def handle_process_finished(self, exit_code, exit_status):
        self.view.append_console_text(f"\n--- Process finished with exit code {exit_code} ---\n")
        self.view.set_running_state(False)

    def stop_application(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.view.append_console_text("\n--- Stopping process... ---\n", is_error=True)
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
            self.view.set_running_state(False)

    def show_about_dialog(self):
        from app.views.mvc_sync.about import AboutDialog
        dialog = AboutDialog(self.view)
        dialog.exec()
