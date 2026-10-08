"""Convert a workbook to HTML with one section per data row.

Each row keeps its sheet, row number and every column, including blank ones,
so an unanswered question is not mistaken for a missing record.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Sequence

from .normalize import clean_text

BLANK = "（空白）"
NUMBERING = {"no", "no.", "#", "編號", "序號", "項次"}
PENDING = ("待確認", "待補充", "待與")


def convert_workbook(
    path: Path,
    title: str,
    *,
    exclude_columns: Sequence[str] = (),
    exclude_row_markers: Sequence[str] = (),
) -> tuple[str, dict[str, Any]]:
    """Convert every sheet.

    A row is left out when any of its cells equals one of `exclude_row_markers`.
    Columns named in `exclude_columns` are not published; when such a cell says
    the answer is still pending, only that status is kept.
    """

    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    body: list[str] = []
    report: dict[str, Any] = {"sheets": 0, "records": 0, "blank_cells": 0, "excluded_rows": 0}
    hidden, markers = set(exclude_columns), set(exclude_row_markers)
    for sheet in workbook.worksheets:
        report["sheets"] += 1
        body.append(f"<h2>工作表：{escape(sheet.title)}</h2>")
        header: list[tuple[int, str]] = []
        for number, row in enumerate(sheet.iter_rows(values_only=True), 1):
            values = [clean_text(str(value)).strip() if value is not None else "" for value in row]
            filled = [(index, value) for index, value in enumerate(values) if value]
            if not filled:
                continue
            if len(filled) == 1:  # a caption such as a section label
                body.append(f"<h3>{escape(filled[0][1])}</h3>")
                continue
            if not header or {value for _, value in filled} == {name for _, name in header}:
                header = filled
                continue
            content = [(name, values[index] if index < len(values) else "") for index, name in header]
            if markers & {value for _, value in content}:
                report["excluded_rows"] += 1
                continue
            pending = any(name in hidden and any(word in value for word in PENDING) for name, value in content)
            content = [(name, value) for name, value in content if name not in hidden]
            # The first column is usually a running number; the next one names the record.
            label = next((value for _, value in content[1:] if value), content[0][1])
            body.append(f"<h3>{escape(sheet.title)} 第 {number} 列：{escape(label[:60])}</h3>")
            for name, value in content:
                if not value and name.lower() in NUMBERING:
                    continue
                if not value:
                    report["blank_cells"] += 1
                text = escape(value or BLANK).replace("\n", "<br>")
                body.append(f"<p><b>{escape(name)}</b>：{text}</p>")
            if pending:
                body.append("<p><b>狀態</b>：此題內容尚待確認</p>")
            report["records"] += 1
    workbook.close()
    html = (f"<!doctype html>\n<html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
            f"<title>{escape(title)}</title></head>\n<body>\n<h1>{escape(title)}</h1>\n"
            + "\n".join(body) + "\n</body></html>\n")
    return html, report
