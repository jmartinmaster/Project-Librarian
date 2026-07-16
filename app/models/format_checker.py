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
"""Code formatting audit scanner for Python and C."""

from __future__ import annotations

import re
from pathlib import Path


class FormatChecker:
    """Formatter checking engine for Python and C source code files."""

    @staticmethod
    def check_format(
        path: str, content: str, enabled_rules: dict[str, bool] | None = None
    ) -> list[dict[str, object]]:
        """Run formatting checks based on file extension."""
        ext = Path(path).suffix.lower()
        if ext == ".py":
            return FormatChecker.check_python_format(path, content, enabled_rules)
        elif ext in (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"):
            return FormatChecker.check_c_format(path, content, enabled_rules)
        return []

    @staticmethod
    def parse_brackets_and_strings(
        content: str, path: str, is_python: bool
    ) -> tuple[list[dict[str, object]], set[int], dict[int, list[tuple[str, int]]], dict[int, str]]:
        """Scans the content character by character.

        Returns:
            - errors: list of mismatched/unclosed bracket/string errors.
            - multiline_lines: set of line numbers inside block comments/multi-line strings.
            - line_bracket_types: dict mapping 1-based line number to open bracket tuples (char, open_line) at end of line.
            - clean_lines: dict mapping 1-based line number to code with strings/comments stripped out.
        """
        errors: list[dict[str, object]] = []
        bracket_stack: list[tuple[str, int, int]] = []
        multiline_lines: set[int] = set()
        line_bracket_types: dict[int, list[tuple[str, int]]] = {}
        clean_lines: dict[int, str] = {}

        lines = content.splitlines(keepends=True)
        n = len(content)
        i = 0
        line = 1
        col = 1

        in_string: str | None = None
        in_comment: str | None = None  # 'line' or 'block'

        current_clean_chars: list[str] = []

        while i < n:
            char = content[i]

            if char == "\n":
                # End of line processing
                if in_comment == "line":
                    in_comment = None
                elif in_comment == "block":
                    multiline_lines.add(line)
                elif in_string:
                    if is_python and in_string in ("'''", '"""'):
                        multiline_lines.add(line)
                    else:
                        # Single-line string unclosed at newline
                        is_escaped = False
                        back_idx = i - 1
                        if back_idx >= 0 and content[back_idx] == "\r":
                            back_idx -= 1
                        if back_idx >= 0 and content[back_idx] == "\\":
                            bs_count = 0
                            while back_idx >= 0 and content[back_idx] == "\\":
                                bs_count += 1
                                back_idx -= 1
                            if bs_count % 2 == 1:
                                is_escaped = True

                        if not is_escaped:
                            errors.append(
                                {
                                    "path": path,
                                    "line": line,
                                    "match": in_string,
                                    "preset_name": "Formatting: Unclosed String",
                                    "description": f"Unclosed string literal starting with {in_string}",
                                    "severity": "error",
                                    "content": lines[line - 1].strip(),
                                }
                            )
                            in_string = None

                line_bracket_types[line] = [(item[0], item[1]) for item in bracket_stack]
                clean_lines[line] = "".join(current_clean_chars)
                current_clean_chars = []

                line += 1
                col = 1
                i += 1
                continue

            if char == "\r":
                i += 1
                continue

            if in_comment == "block":
                if not is_python and content[i : i + 2] == "*/":
                    in_comment = None
                    i += 2
                    col += 2
                else:
                    i += 1
                    col += 1
                continue

            if in_comment == "line":
                i += 1
                col += 1
                continue

            if in_string:
                if char == "\\":
                    # Escape character
                    i += 2
                    col += 2
                    continue
                if is_python and in_string in ("'''", '"""'):
                    if content[i : i + 3] == in_string:
                        in_string = None
                        i += 3
                        col += 3
                    else:
                        i += 1
                        col += 1
                else:
                    if char == in_string:
                        in_string = None
                        i += 1
                        col += 1
                    else:
                        i += 1
                        col += 1
                continue

            # Not in comment, not in string
            # Check comment start
            if is_python:
                if char == "#":
                    in_comment = "line"
                    i += 1
                    col += 1
                    continue
            else:
                if content[i : i + 2] == "//":
                    in_comment = "line"
                    i += 2
                    col += 2
                    continue
                elif content[i : i + 2] == "/*":
                    in_comment = "block"
                    i += 2
                    col += 2
                    continue

            # Check string start
            if is_python:
                if content[i : i + 3] in ("'''", '"""'):
                    in_string = content[i : i + 3]
                    i += 3
                    col += 3
                    continue
                elif char in ("'", '"'):
                    in_string = char
                    i += 1
                    col += 1
                    continue
            else:
                if char in ("'", '"'):
                    in_string = char
                    i += 1
                    col += 1
                    continue

            # Check brackets
            if char in ("(", "[", "{"):
                bracket_stack.append((char, line, col))
                current_clean_chars.append(char)
                i += 1
                col += 1
                continue
            elif char in (")", "]", "}"):
                matching = {")": "(", "]": "[", "}": "{"}
                expected = matching[char]
                if not bracket_stack:
                    errors.append(
                        {
                            "path": path,
                            "line": line,
                            "match": char,
                            "preset_name": "Formatting: Mismatched Bracket",
                            "description": f"Extra close bracket '{char}' without matching open bracket",
                            "severity": "error",
                            "content": lines[line - 1].strip(),
                        }
                    )
                else:
                    open_char, open_line, open_col = bracket_stack.pop()
                    if open_char != expected:
                        errors.append(
                            {
                                "path": path,
                                "line": line,
                                "match": char,
                                "preset_name": "Formatting: Mismatched Bracket",
                                "description": f"Mismatched bracket: '{char}' closed open bracket '{open_char}' from line {open_line}",
                                "severity": "error",
                                "content": lines[line - 1].strip(),
                            }
                        )
                current_clean_chars.append(char)
                i += 1
                col += 1
                continue

            current_clean_chars.append(char)
            i += 1
            col += 1

        # Capture last line depth and content if not ending with \n
        if current_clean_chars or line not in clean_lines:
            line_bracket_types[line] = [(item[0], item[1]) for item in bracket_stack]
            clean_lines[line] = "".join(current_clean_chars)

        # EOF checks
        if in_string:
            errors.append(
                {
                    "path": path,
                    "line": line - 1 if line > 1 else 1,
                    "match": in_string,
                    "preset_name": "Formatting: Unclosed String",
                    "description": f"Unclosed string literal starting with {in_string} at end of file",
                    "severity": "error",
                    "content": lines[-1].strip() if lines else "",
                }
            )

        while bracket_stack:
            open_char, open_line, open_col = bracket_stack.pop()
            errors.append(
                {
                    "path": path,
                    "line": open_line,
                    "match": open_char,
                    "preset_name": "Formatting: Unclosed Bracket",
                    "description": f"Unclosed open bracket '{open_char}'",
                    "severity": "error",
                    "content": lines[open_line - 1].strip() if open_line <= len(lines) else "",
                }
            )

        return errors, multiline_lines, line_bracket_types, clean_lines

    @staticmethod
    def is_c_continuation(
        line_idx: int,
        open_brackets: list[tuple[str, int]],
        clean_lines: dict[int, str],
    ) -> bool:
        """Determines if the line is a continuation of a C statement from a previous line."""
        for char, open_line in open_brackets:
            if char in ("(", "["):
                if open_line < line_idx:
                    # Check if there is a statement terminator between open_line and line_idx
                    has_terminator = False
                    for l in range(open_line, line_idx):
                        l_clean = clean_lines.get(l, "")
                        if ";" in l_clean or "{" in l_clean or "}" in l_clean:
                            has_terminator = True
                            break
                    if not has_terminator:
                        return True
        return False

    @staticmethod
    def is_python_continuation(
        line_idx: int,
        open_brackets: list[tuple[str, int]],
        clean_lines: dict[int, str],
        lines: list[str],
    ) -> bool:
        """Determines if the line is a continuation inside brackets of a Python statement from a previous line."""
        current_indent = len(lines[line_idx - 1]) - len(lines[line_idx - 1].lstrip())
        for char, open_line in open_brackets:
            if open_line < line_idx:
                open_indent = len(lines[open_line - 1]) - len(lines[open_line - 1].lstrip())
                if open_indent >= current_indent:
                    continue
                # Check if there is a statement boundary between open_line and line_idx
                has_boundary = False
                for l in range(open_line + 1, line_idx):
                    l_clean = clean_lines.get(l, "").strip()
                    if l_clean:
                        first_word = l_clean.split()[0]
                        if first_word in ("def", "class", "if", "elif", "for", "while", "except", "else", "try", "finally"):
                            l_indent = len(lines[l - 1]) - len(lines[l - 1].lstrip())
                            if l_indent <= open_indent:
                                has_boundary = True
                                break
                if not has_boundary:
                    return True
        return False

    @staticmethod
    def check_python_format(
        path: str, content: str, enabled_rules: dict[str, bool] | None = None
    ) -> list[dict[str, object]]:
        """Performs Python-specific formatting checks."""
        results: list[dict[str, object]] = []

        # 1. Bracket and string checks
        bracket_errors, multiline_lines, line_bracket_types, clean_lines = (
            FormatChecker.parse_brackets_and_strings(content, path, is_python=True)
        )
        results.extend(bracket_errors)

        lines = content.splitlines()

        # Track spaces vs tabs across the file
        has_spaces = False
        has_tabs = False

        consecutive_blank_lines = 0

        for line_idx, line in enumerate(lines, start=1):
            if line_idx in multiline_lines:
                consecutive_blank_lines = 0
                continue
            stripped = line.strip()

            # Check mixed indentation
            indent_match = re.match(r"^([ \t]+)", line)
            if indent_match:
                indent = indent_match.group(1)
                if " " in indent and "\t" in indent:
                    results.append(
                        {
                            "path": path,
                            "line": line_idx,
                            "match": indent,
                            "preset_name": "Formatting: Mixed Indentation",
                            "description": "Indentation contains both spaces and tabs",
                            "severity": "warning",
                            "content": line.strip(),
                        }
                    )
                elif " " in indent:
                    has_spaces = True
                    # Inconsistent Python spacing check (not multiple of 4)
                    if len(indent) % 4 != 0:
                        results.append(
                            {
                                "path": path,
                                "line": line_idx,
                                "match": indent,
                                "preset_name": "Formatting: Inconsistent Indentation",
                                "description": f"Indentation of {len(indent)} spaces is not a multiple of 4",
                                "severity": "warning",
                                "content": line.strip(),
                            }
                        )
                elif "\t" in indent:
                    has_tabs = True

            # Check trailing whitespace
            if line and (line[-1] == " " or line[-1] == "\t"):
                trailing_ws = re.search(r"([ \t]+)$", line)
                results.append(
                    {
                        "path": path,
                        "line": line_idx,
                        "match": trailing_ws.group(1) if trailing_ws else " ",
                        "preset_name": "Formatting: Trailing Whitespace",
                        "description": "Line contains trailing whitespace",
                        "severity": "info",
                        "content": line.strip(),
                    }
                )

            # Check consecutive blank lines
            if not stripped:
                consecutive_blank_lines += 1
                if consecutive_blank_lines > 2:
                    results.append(
                        {
                            "path": path,
                            "line": line_idx,
                            "match": "\\n",
                            "preset_name": "Formatting: Too Many Blank Lines",
                            "description": f"Found {consecutive_blank_lines} consecutive blank lines (max 2)",
                            "severity": "info",
                            "content": "",
                        }
                    )
            else:
                consecutive_blank_lines = 0

            # Check line length (warn if > 88 characters)
            if len(line) > 88:
                results.append(
                    {
                        "path": path,
                        "line": line_idx,
                        "match": line[88:],
                        "preset_name": "Formatting: Line Too Long",
                        "description": f"Line length exceeds 88 characters ({len(line)} chars)",
                        "severity": "info",
                        "content": line.strip(),
                    }
                )

            # Check missing colons at end of python block headers
            if line_idx not in multiline_lines:
                clean_line = clean_lines.get(line_idx, "").strip()
                if clean_line:
                    words = clean_line.split()
                    if words:
                        first_word = words[0]
                        # check block statement keywords
                        is_block_keyword = False
                        if first_word in ("def", "class", "if", "elif", "for", "while", "except"):
                            is_block_keyword = True
                        elif first_word in ("else", "try", "finally") and (
                            clean_line == first_word or clean_line.startswith(first_word + ":")
                        ):
                            is_block_keyword = True

                        if is_block_keyword:
                            # If it's a 'for' or 'if' and is inside brackets of the current statement,
                            # it's a comprehension, so skip it.
                            open_types = line_bracket_types.get(line_idx, [])
                            if first_word in ("for", "if") and FormatChecker.is_python_continuation(line_idx, open_types, clean_lines, lines):
                                is_block_keyword = False

                        if is_block_keyword:
                            # Start stack size is the stack size at the end of the previous line (or 0)
                            start_stack = line_bracket_types.get(line_idx - 1, []) if line_idx > 1 else []
                            start_stack_size = len(start_stack)
                            
                            # If the first line itself has no open brackets (relative to start) and no backslash,
                            # the statement is already complete on this line.
                            first_line_stack_size = len(line_bracket_types.get(line_idx, []))
                            first_line_ends_with_backslash = lines[line_idx - 1].rstrip().endswith("\\")
                            
                            if first_line_stack_size <= start_stack_size and not first_line_ends_with_backslash:
                                end_line_idx = line_idx
                            else:
                                # Scan forward to find the end of the statement
                                start_indent_len = len(line) - len(line.lstrip())
                                end_line_idx = line_idx + 1
                                while end_line_idx <= len(lines):
                                    curr_stack_size = len(line_bracket_types.get(end_line_idx, []))
                                    ends_with_backslash = lines[end_line_idx - 1].rstrip().endswith("\\")
                                    if curr_stack_size <= start_stack_size and not ends_with_backslash:
                                        break
                                        
                                    if end_line_idx < len(lines):
                                        next_line = lines[end_line_idx]
                                        next_stripped = next_line.strip()
                                        if next_stripped:
                                            next_indent_len = len(next_line) - len(next_line.lstrip())
                                            next_words = next_stripped.split()
                                            next_first_word = next_words[0] if next_words else ""
                                            is_next_block = next_first_word in ("def", "class", "if", "elif", "for", "while", "except", "else", "try", "finally")
                                            if next_indent_len <= start_indent_len:
                                                if not next_stripped.startswith((")", "]", "}")):
                                                    break
                                            elif is_next_block and curr_stack_size <= start_stack_size:
                                                break
                                    end_line_idx += 1
                            
                            if end_line_idx > len(lines):
                                end_line_idx = len(lines)
                                
                            end_clean_line = clean_lines.get(end_line_idx, "").strip()
                            if not end_clean_line.endswith(":"):
                                results.append(
                                    {
                                        "path": path,
                                        "line": line_idx,
                                        "match": clean_line.split()[0] if clean_line else "",
                                        "preset_name": "Formatting: Missing Colon",
                                        "description": f"Block header starting with '{first_word}' is missing a trailing colon ':'",
                                        "severity": "error",
                                        "content": line.strip(),
                                    }
                                )

        # Check overall mixed indentation across the file
        if has_spaces and has_tabs:
            results.append(
                {
                    "path": path,
                    "line": 1,
                    "match": "spaces and tabs",
                    "preset_name": "Formatting: File Mixed Indentation",
                    "description": "File contains a mix of space-indented and tab-indented lines",
                    "severity": "warning",
                    "content": "",
                }
            )

        # Check missing end-of-file newline
        if content and not content.endswith("\n"):
            results.append(
                {
                    "path": path,
                    "line": len(lines) if lines else 1,
                    "match": "\\no-newline",
                    "preset_name": "Formatting: Missing Final Newline",
                    "description": "File does not end with a final newline character",
                    "severity": "info",
                    "content": lines[-1].strip() if lines else "",
                }
            )

        if enabled_rules is not None:
            results = [
                r for r in results 
                if enabled_rules.get(str(r.get("preset_name", "")).replace("Formatting: ", ""), True)
            ]
        return results

    @staticmethod
    def check_c_format(
        path: str, content: str, enabled_rules: dict[str, bool] | None = None
    ) -> list[dict[str, object]]:
        """Performs C-specific formatting checks."""
        results: list[dict[str, object]] = []

        # 1. Bracket and string checks
        bracket_errors, multiline_lines, line_bracket_types, clean_lines = (
            FormatChecker.parse_brackets_and_strings(content, path, is_python=False)
        )
        results.extend(bracket_errors)

        lines = content.splitlines()

        has_spaces = False
        has_tabs = False
        consecutive_blank_lines = 0

        for line_idx, line in enumerate(lines, start=1):
            if line_idx in multiline_lines:
                consecutive_blank_lines = 0
                continue
            stripped = line.strip()

            # Check mixed indentation
            indent_match = re.match(r"^([ \t]+)", line)
            if indent_match:
                indent = indent_match.group(1)
                if " " in indent and "\t" in indent:
                    results.append(
                        {
                            "path": path,
                            "line": line_idx,
                            "match": indent,
                            "preset_name": "Formatting: Mixed Indentation",
                            "description": "Indentation contains both spaces and tabs",
                            "severity": "warning",
                            "content": line.strip(),
                        }
                    )
                elif " " in indent:
                    has_spaces = True
                elif "\t" in indent:
                    has_tabs = True

            # Check trailing whitespace
            if line and (line[-1] == " " or line[-1] == "\t"):
                trailing_ws = re.search(r"([ \t]+)$", line)
                results.append(
                    {
                        "path": path,
                        "line": line_idx,
                        "match": trailing_ws.group(1) if trailing_ws else " ",
                        "preset_name": "Formatting: Trailing Whitespace",
                        "description": "Line contains trailing whitespace",
                        "severity": "info",
                        "content": line.strip(),
                    }
                )

            # Check consecutive blank lines
            if not stripped:
                consecutive_blank_lines += 1
                if consecutive_blank_lines > 2:
                    results.append(
                        {
                            "path": path,
                            "line": line_idx,
                            "match": "\\n",
                            "preset_name": "Formatting: Too Many Blank Lines",
                            "description": f"Found {consecutive_blank_lines} consecutive blank lines (max 2)",
                            "severity": "info",
                            "content": "",
                        }
                    )
            else:
                consecutive_blank_lines = 0

            # Check line length (warn if > 80 characters for C standard style)
            if len(line) > 80:
                results.append(
                    {
                        "path": path,
                        "line": line_idx,
                        "match": line[80:],
                        "preset_name": "Formatting: Line Too Long",
                        "description": f"Line length exceeds 80 characters ({len(line)} chars)",
                        "severity": "info",
                        "content": line.strip(),
                    }
                )

            # Check missing semicolons
            if line_idx not in multiline_lines:
                clean_line = clean_lines.get(line_idx, "").strip()
                # Skip preprocessor directives
                if clean_line and not line.strip().startswith("#"):
                    # Semicolons are not required if line ends with:
                    # - semicolon itself (;)
                    # - open brace or close brace ({, })
                    # - comma (,) indicating continuation
                    # - backslash (\) indicating macro/line continuation
                    # - colon (:) indicating label (case, default, public, etc.)
                    # - or if bracket depth at end of line is > 0
                    # Control flow headers are also skipped:
                    # if, else, for, while, switch, do, struct, union, class, namespace, enum
                    words = clean_line.split()
                    if words:
                        first_word = words[0]
                        control_flow = (
                            "if",
                            "else",
                            "for",
                            "while",
                            "switch",
                            "do",
                            "struct",
                            "union",
                            "class",
                            "namespace",
                            "enum",
                        )
                        if first_word not in control_flow:
                            open_types = line_bracket_types.get(line_idx, [])
                            is_continuation = FormatChecker.is_c_continuation(line_idx, open_types, clean_lines)
                            has_curr_bracket = any(t[0] in ("(", "[") and t[1] == line_idx for t in open_types)
                            if not is_continuation and not has_curr_bracket:
                                last_char = clean_line[-1]
                                if last_char not in (";", "{", "}", ",", "\\", ":"):
                                    # Peek next non-empty line to check if function header
                                    is_func_header = False
                                    next_idx = line_idx
                                    while next_idx < len(lines):
                                        next_line_stripped = lines[next_idx].strip()
                                        if next_line_stripped:
                                            if next_line_stripped.startswith("{"):
                                                is_func_header = True
                                            break
                                        next_idx += 1

                                    if not is_func_header:
                                        results.append(
                                            {
                                                "path": path,
                                                "line": line_idx,
                                                "match": last_char,
                                                "preset_name": "Formatting: Missing Semicolon",
                                                "description": "Statement is missing a trailing semicolon ';'",
                                                "severity": "error",
                                                "content": line.strip(),
                                            }
                                        )

        # Check overall mixed indentation across the file
        if has_spaces and has_tabs:
            results.append(
                {
                    "path": path,
                    "line": 1,
                    "match": "spaces and tabs",
                    "preset_name": "Formatting: File Mixed Indentation",
                    "description": "File contains a mix of space-indented and tab-indented lines",
                    "severity": "warning",
                    "content": "",
                }
            )

        # Check missing end-of-file newline
        if content and not content.endswith("\n"):
            results.append(
                {
                    "path": path,
                    "line": len(lines) if lines else 1,
                    "match": "\\no-newline",
                    "preset_name": "Formatting: Missing Final Newline",
                    "description": "File does not end with a final newline character",
                    "severity": "info",
                    "content": lines[-1].strip() if lines else "",
                }
            )

        if enabled_rules is not None:
            results = [
                r for r in results 
                if enabled_rules.get(str(r.get("preset_name", "")).replace("Formatting: ", ""), True)
            ]
        return results
