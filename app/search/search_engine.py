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


def _best_preview_for_query(text: str, query: str, tokens: list[str]) -> tuple[int | None, str]:
    """Return the most relevant line number and text snippet for a query."""
    for line_number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if query in lowered or all(token in lowered for token in tokens):
            snippet = line.strip()
            return line_number, snippet[:180]

    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return (1 if first else None), first[:180]


def _score_text_record(path: str, text: str, query: str, tokens: list[str]) -> int:
    score = 0
    lowered = text.lower()
    path_lower = path.lower()
    if query in path_lower:
        score += 80
    if query in lowered:
        score += 25
    for token in tokens:
        if token in path_lower:
            score += 10
        if token in lowered:
            score += 5
    return score


def _score_symbol_record(symbol: dict[str, object], query: str, tokens: list[str]) -> int:
    haystack = " ".join(
        [
            str(symbol.get("name", "")),
            str(symbol.get("qualified_name", "")),
            str(symbol.get("signature", "")),
            str(symbol.get("path", "")),
        ]
    ).lower()
    score = 0
    if query in str(symbol.get("qualified_name", "")).lower():
        score += 90
    if query in str(symbol.get("name", "")).lower():
        score += 60
    for token in tokens:
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
) -> list[dict[str, object]]:
    """Search indexed data and return ranked mixed-type records."""
    query_text = query.strip().lower()
    if not query_text:
        return []

    tokens = [token.lower() for token in TOKEN_PATTERN.findall(query_text)] or [query_text]
    results: list[dict[str, object]] = []

    if scope in {"all", "files"}:
        for path, text in file_corpus.items():
            score = _score_text_record(path=path, text=text, query=query_text, tokens=tokens)
            if score <= 0:
                continue
            preview_line, preview = _best_preview_for_query(text=text, query=query_text, tokens=tokens)
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

    if scope in {"all", "symbols"}:
        for symbol in symbols:
            score = _score_symbol_record(symbol=symbol, query=query_text, tokens=tokens)
            if score <= 0:
                continue
            results.append(
                {
                    "type": "symbol",
                    "file_type": _file_type_from_path(str(symbol.get("path", ""))),
                    "path": symbol.get("path"),
                    "line": symbol.get("line"),
                    "title": symbol.get("qualified_name"),
                    "preview": symbol.get("signature") or symbol.get("kind"),
                    "score": score,
                }
            )

    if scope in {"all", "excel"}:
        for row in excel_rows:
            combined = " ".join([str(row.get("field", "")), str(row.get("value", "")), str(row.get("file", ""))]).lower()
            if query_text not in combined and not all(token in combined for token in tokens):
                continue
            score = 55 + sum(5 for token in tokens if token in combined)
            results.append(
                {
                    "type": "excel",
                    "file_type": _file_type_from_path(str(row.get("file", ""))),
                    "path": row.get("file"),
                    "line": row.get("row"),
                    "title": row.get("field"),
                    "preview": row.get("value"),
                    "score": score,
                }
            )

    results.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("path", "")), int(item.get("line") or 0)))
    return results[: max(1, int(limit))]
