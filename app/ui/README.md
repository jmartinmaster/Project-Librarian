# UI Package

This package contains PyQt6 view/controller components.

Rules:
- Keep business logic out of UI widgets.
- Use index_manager and search_engine from controller code paths.
- Keep layout changes in Qt Designer form files under app/ui/forms/.
- Load .ui files at runtime using PyQt6 uic.loadUi so manual UI edits do not require code regeneration.
