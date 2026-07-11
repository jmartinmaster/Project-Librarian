# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Project Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.

"""Search engine for file text, symbols, and spreadsheet keyword rows."""

from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")


def _file_type_from_path(path: str | None) -> str:
    """Return normalized file type label derived from a result path."""
    if not path:
        return ""
    _, dot, suffix = str(path).rpartition(".")
    if not dot or not suffix:
        return ""
    return suffix.lower()


def _best_preview_for_query(
    text: str, query: str, tokens: list[str], match_case: bool, pattern: re.Pattern | None
) -> tuple[int | None, str]:
    """Return the most relevant line number and text snippet for a query."""
    for line_number, line in enumerate(text.splitlines(), start=1):
        if pattern is not None:
            if pattern.search(line):
                return line_number, line.strip()[:180]
        else:
            if match_case:
                if query in line or all(token in line for token in tokens):
                    return line_number, line.strip()[:180]
            else:
                lowered = line.lower()
                if query in lowered or all(token in lowered for token in tokens):
                    return line_number, line.strip()[:180]

    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return (1 if first else None), first[:180]


def _score_text_record(
    path: str, text: str, query: str, tokens: list[str], match_case: bool, pattern: re.Pattern | None
) -> int:
    score = 0
    if pattern is not None:
        if pattern.search(path):
            score += 80
        if pattern.search(text):
            score += 25
        return score

    h_path = path if match_case else path.lower()
    h_text = text if match_case else text.lower()
    q = query if match_case else query.lower()
    t_tokens = tokens if match_case else [t.lower() for t in tokens]

    if q in h_path:
        score += 80
    if q in h_text:
        score += 25
    for token in t_tokens:
        if token in h_path:
            score += 10
        if token in h_text:
            score += 5
    return score


def _score_symbol_record(
    symbol: dict[str, object], query: str, tokens: list[str], match_case: bool, pattern: re.Pattern | None
) -> int:
    name = str(symbol.get("name", ""))
    qualified_name = str(symbol.get("qualified_name", ""))
    signature = str(symbol.get("signature", ""))
    path = str(symbol.get("path", ""))

    if pattern is not None:
        score = 0
        if pattern.search(qualified_name):
            score += 90
        elif pattern.search(name):
            score += 60
        elif pattern.search(signature) or pattern.search(path):
            score += 10
        return score

    h_name = name if match_case else name.lower()
    h_qual = qualified_name if match_case else qualified_name.lower()
    h_sig = signature if match_case else signature.lower()
    h_path = path if match_case else path.lower()
    q = query if match_case else query.lower()
    t_tokens = tokens if match_case else [t.lower() for t in tokens]

    score = 0
    if q in h_qual:
        score += 90
    if q in h_name:
        score += 60

    haystack = " ".join([h_name, h_qual, h_sig, h_path])
    for token in t_tokens:
        if token in haystack:
            score += 10
    return score


def search_snapshot(
    file_corpus: dict[str, str],
    symbols: list[dict[str, object]],
    excel_rows: list[dict[str, object]],
    query: str,
    scope: str = "all",
    limit: int = 20,
    match_case: bool = False,
    use_regex: bool = False,
) -> list[dict[str, object]]:
    """Search indexed data and return ranked mixed-type records."""
    if not query.strip():
        return []

    pattern = None
    if use_regex:
        try:
            flags = 0 if match_case else re.IGNORECASE
            pattern = re.compile(query, flags)
        except re.error:
            pass  # Fall back to literal search

    query_term = query if match_case else query.lower()
    tokens = [token if match_case else token.lower() for token in TOKEN_PATTERN.findall(query)] or [query_term]

    results: list[dict[str, object]] = []

    if scope in {"all", "files"}:
        for path, text in file_corpus.items():
            score = _score_text_record(path, text, query, tokens, match_case, pattern)
            if score <= 0:
                continue
            preview_line, preview = _best_preview_for_query(text, query, tokens, match_case, pattern)
            results.append(
                {
                    "type": "file",
                    "file_type": _file_type_from_path(path),
                    "path": path,
                    "line": preview_line,
                    "preview": preview,
                    "score": score,
                }
            )

    if scope in {"all", "symbols", "ast", "cst"}:
        for symbol in symbols:
            score = _score_symbol_record(symbol, query, tokens, match_case, pattern)
            if score <= 0:
                continue
            
            result_type = "symbol"
            if scope == "ast":
                result_type = "ast_node"
            elif scope == "cst":
                result_type = "cst_node"
                
            results.append(
                {
                    "type": result_type,
                    "file_type": _file_type_from_path(str(symbol.get("path", ""))),
                    "path": symbol.get("path"),
                    "line": symbol.get("line"),
                    "title": symbol.get("qualified_name"),
                    "preview": symbol.get("signature") or symbol.get("kind"),
                    "kind": symbol.get("kind"),
                    "doc_summary": symbol.get("doc_summary", ""),
                    "score": score,
                }
            )

    if scope in {"all", "excel"}:
        for row in excel_rows:
            field_val = str(row.get("field", ""))
            value_val = str(row.get("value", ""))
            file_val = str(row.get("file", ""))

            if pattern is not None:
                if not (pattern.search(field_val) or pattern.search(value_val) or pattern.search(file_val)):
                    continue
                score = 65
            else:
                combined = " ".join([field_val, value_val, file_val])
                if not match_case:
                    combined = combined.lower()

                if query_term not in combined and not all(token in combined for token in tokens):
                    continue
                score = 55 + sum(5 for token in tokens if token in combined)

            results.append(
                {
                    "type": "excel",
                    "file_type": _file_type_from_path(file_val),
                    "path": file_val,
                    "line": row.get("row"),
                    "title": field_val,
                    "preview": value_val,
                    "score": score,
                }
            )

    results.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("path", "")), int(item.get("line") or 0)))
    return results[: max(1, int(limit))]
