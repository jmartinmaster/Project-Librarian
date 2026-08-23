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
"""Centralized context menu builder and dispatcher across all views."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QPoint, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QMenu, QWidget


@dataclass
class ItemContext:
    """Standard metadata extracted from any right-clicked item in the IDE."""

    path: str = ""
    line: int | None = None
    symbol: str = ""
    source: str = "Application"
    title: str = ""
    snippet: str = ""
    can_open: bool = True
    can_copy_path: bool = True
    can_copy_ref: bool = True
    can_create_note: bool = True
    can_trace_calls: bool = True
    extra_actions: list[tuple[str, Callable[[], None]]] = field(default_factory=list)


@dataclass
class ContextMenuCallbacks:
    """Optional callbacks for actions dispatched by the centralized menu."""

    open_file: Callable[[str, int | None], None] | None = None
    open_external: Callable[[str], None] | None = None
    create_note: Callable[[str, int, str, str, str, str], None] | None = None
    trace_symbol: Callable[[str], None] | None = None


class ContextMenuBuilder:
    """Builds and executes unified, standard context menus with section-specific actions."""

    @classmethod
    def build_menu(
        cls,
        parent: QWidget,
        ctx: ItemContext,
        callbacks: ContextMenuCallbacks | None = None,
    ) -> QMenu:
        """Create and populate a standard QMenu from the given ItemContext."""
        menu = QMenu(parent)
        cb = callbacks or ContextMenuCallbacks()

        # 1. Open Actions
        if ctx.path and ctx.can_open:
            act_open = menu.addAction("Open in Editor")
            if cb.open_file:
                act_open.triggered.connect(lambda: cb.open_file(ctx.path, ctx.line))

            act_external = menu.addAction("Open Externally")
            if cb.open_external:
                act_external.triggered.connect(lambda: cb.open_external(ctx.path))
            else:
                act_external.triggered.connect(lambda: cls._default_open_external(ctx.path))

            menu.addSeparator()

        # 2. Symbol / Hierarchy Actions
        if ctx.symbol and ctx.can_trace_calls and cb.trace_symbol:
            act_trace = menu.addAction(f"Trace '{ctx.symbol}' Call Hierarchy")
            act_trace.triggered.connect(lambda: cb.trace_symbol(ctx.symbol))
            menu.addSeparator()

        # 3. Note Creation Action
        if ctx.can_create_note:
            act_note = menu.addAction("📝 New Note for Item")
            if cb.create_note:
                t_line = ctx.line if (isinstance(ctx.line, int) and ctx.line > 0) else 1
                t_title = ctx.title or f"Note: {ctx.symbol or Path(ctx.path).name or 'Item'}"
                act_note.triggered.connect(
                    lambda: cb.create_note(
                        ctx.path,
                        t_line,
                        ctx.symbol,
                        ctx.source,
                        t_title,
                        ctx.snippet,
                    )
                )
            menu.addSeparator()

        # 4. Copy Actions
        if ctx.path and ctx.can_copy_path:
            act_copy_path = menu.addAction("Copy Path")
            act_copy_path.triggered.connect(lambda: cls._copy_path_to_clipboard(ctx.path))

        if ctx.path and ctx.can_copy_ref:
            act_copy_ref = menu.addAction("Copy Reference Location")
            act_copy_ref.triggered.connect(lambda: cls._copy_ref_to_clipboard(ctx.path, ctx.line))

        # 5. Section-Specific Extra Actions
        if ctx.extra_actions:
            menu.addSeparator()
            for label, action_handler in ctx.extra_actions:
                act_extra = menu.addAction(label)
                act_extra.triggered.connect(action_handler)

        return menu

    @classmethod
    def exec_menu(
        cls,
        parent: QWidget,
        global_pos: QPoint,
        ctx: ItemContext,
        callbacks: ContextMenuCallbacks | None = None,
    ) -> None:
        """Construct and execute the menu at global_pos."""
        menu = cls.build_menu(parent, ctx, callbacks)
        menu.exec(global_pos)

    @staticmethod
    def _copy_path_to_clipboard(path_text: str) -> None:
        folder = Path(path_text).parent.as_posix() if Path(path_text).is_file() else path_text
        QApplication.clipboard().setText(folder or path_text)

    @staticmethod
    def _copy_ref_to_clipboard(path_text: str, line: int | None) -> None:
        ref = f"{path_text}:{line}" if line is not None else path_text
        QApplication.clipboard().setText(ref)

    @staticmethod
    def _default_open_external(path_text: str) -> None:
        path = Path(path_text).resolve()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
