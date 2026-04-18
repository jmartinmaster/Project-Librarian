"""Smoke tests for Excel and CSV indexing helpers."""

from __future__ import annotations

from pathlib import Path

from app.indexer.excel_indexer import discover_headers, index_excel_rows


def test_csv_headers_and_rows(tmp_path: Path):
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("Code,Part Number\nD01,PN-1\n", encoding="utf-8")

    headers = discover_headers(csv_path)
    assert headers == ["Code", "Part Number"]

    rows = index_excel_rows(tmp_path, ["Part Number"], limit=20)
    assert rows
    assert rows[0]["field"] == "Part Number"
    assert rows[0]["value"] == "PN-1"


def test_invalid_xlsx_is_skipped_without_crash(tmp_path: Path):
    invalid_xlsx = tmp_path / "broken.xlsx"
    invalid_xlsx.write_bytes(b"not a valid xlsx payload")

    valid_csv = tmp_path / "valid.csv"
    valid_csv.write_text("Code,Part Number\nA1,PN-99\n", encoding="utf-8")

    assert discover_headers(invalid_xlsx) == []

    rows = index_excel_rows(tmp_path, ["Part Number"], limit=20)
    assert rows
    assert rows[0]["value"] == "PN-99"
