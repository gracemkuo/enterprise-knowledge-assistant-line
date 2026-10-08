"""Convert a PDF's own text layer to HTML with real tables.

The managed layout parser re-reads table pages visually and can swap columns.
The text layer already has the right reading order, so cells are located from
the ruling lines and filled with the words in that order.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Sequence

from .normalize import clean_text

Box = tuple[float, float, float, float]  # x0, top, x1, bottom
MIN_PAGE_CHARS = 40
MIN_TEXT_PAGE_SHARE = 0.3


def _inside(word: dict[str, Any], box: Box) -> bool:
    x = (word["x0"] + word["x1"]) / 2
    y = (word["top"] + word["bottom"]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _bands(values: Sequence[float]) -> list[tuple[float, float]]:
    edges: list[float] = []
    for value in sorted(values):
        if not edges or value - edges[-1] > 1.5:
            edges.append(value)
    return list(zip(edges, edges[1:]))


def join_lines(lines: Sequence[str]) -> str:
    """Join wrapped lines; CJK text continues without a space."""

    text = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if text and (text[-1].isascii() or line[0].isascii()):
            text += " "
        text += line
    return text


def table_rows(cells: Sequence[Box], words: Sequence[dict[str, Any]]) -> tuple[list[list[tuple[str, int]]], list[str]]:
    """Return rows of (text, colspan) and the words no cell claimed.

    A cell merged across columns is returned once with its column span. A cell merged across
    rows is repeated on each row so every row can be read on its own.
    """

    texts: list[list[str]] = [[] for _ in cells]
    unassigned: list[str] = []
    for word in words:
        owner = next((i for i, cell in enumerate(cells) if _inside(word, cell)), None)
        if owner is None:
            unassigned.append(word["text"])
        else:
            texts[owner].append(word["text"])
    columns = _bands([x for cell in cells for x in (cell[0], cell[2])])
    rows: list[list[tuple[str, int]]] = []
    for top, bottom in _bands([y for cell in cells for y in (cell[1], cell[3])]):
        y = (top + bottom) / 2
        owners = [
            next((i for i, cell in enumerate(cells)
                  if cell[0] <= (x0 + x1) / 2 <= cell[2] and cell[1] <= y <= cell[3]), None)
            for x0, x1 in columns
        ]
        if all(owner is None for owner in owners):
            continue
        row: list[tuple[str, int]] = []
        previous: object = object()
        for owner in owners:
            if owner is not None and owner == previous:
                row[-1] = (row[-1][0], row[-1][1] + 1)
            else:
                row.append((clean_text(" ".join(texts[owner])) if owner is not None else "", 1))
            previous = owner
        if any(text for text, _ in row) and (not rows or row != rows[-1]):
            rows.append(row)
    return rows, unassigned


def _table_html(rows: list[list[tuple[str, int]]]) -> str:
    lines = ["<table>"]
    for index, row in enumerate(rows):
        tag = "th" if index == 0 else "td"
        # The search service flattens colspan, which shifts later cells under the
        # wrong header, so a merged cell is written once per column it covers.
        cells = "".join(f"<{tag}>{escape(text)}</{tag}>" * span for text, span in row)
        lines.append(f"<tr>{cells}</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _is_table(rows: list[list[tuple[str, int]]]) -> bool:
    filled = [sum(bool(text) for text, _ in row) for row in rows]
    return len(rows) >= 2 and sum(filled) >= 4 and max(filled, default=0) >= 2


def convert_pdf(path: Path, title: str) -> tuple[str | None, dict[str, Any]]:
    """Return (html, report). html is None when the PDF has no usable text layer."""

    import pdfplumber

    body: list[str] = []
    report: dict[str, Any] = {"pages": 0, "text_chars": 0, "tables": 0,
                              "low_text_pages": [], "table_pages_with_unplaced_words": []}
    with pdfplumber.open(path) as pdf:
        report["pages"] = len(pdf.pages)
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(use_text_flow=True)
            chars = sum(len(word["text"]) for word in words)
            report["text_chars"] += chars
            if chars < MIN_PAGE_CHARS:
                report["low_text_pages"].append(number)
            tables = []
            for found in page.find_tables():
                inside = [word for word in words if _inside(word, found.bbox)]
                rows, unassigned = table_rows(found.cells, inside)
                # Charts also have ruling lines; when most words fall outside the
                # cells it is not a table, so leave the page text as it is.
                if _is_table(rows) and len(unassigned) <= len(inside) / 2:
                    tables.append((found.bbox, rows, unassigned))
                    if unassigned and number not in report["table_pages_with_unplaced_words"]:
                        report["table_pages_with_unplaced_words"].append(number)
            report["tables"] += len(tables)
            body.append(f"<h2>第 {number} 頁</h2>")
            emitted: set[int] = set()
            lines: list[str] = []
            last_top: float | None = None

            def flush() -> None:
                text = clean_text(join_lines(lines))
                if text:
                    body.append(f"<p>{escape(text)}</p>")
                lines.clear()

            for word in words:
                owner = next((i for i, table in enumerate(tables) if _inside(word, table[0])), None)
                if owner is not None:
                    if owner not in emitted:
                        flush()
                        body.append(_table_html(tables[owner][1]))
                        if tables[owner][2]:  # keep text the grid could not place
                            body.append(f"<p>{escape(clean_text(' '.join(tables[owner][2])))}</p>")
                        emitted.add(owner)
                    last_top = None
                    continue
                if last_top is None or abs(word["top"] - last_top) > 2:
                    lines.append(word["text"])
                else:
                    lines[-1] += " " + word["text"]
                last_top = word["top"]
            flush()
    low = len(report["low_text_pages"])
    if report["pages"] == 0 or (report["pages"] - low) / report["pages"] < MIN_TEXT_PAGE_SHARE:
        return None, report
    html = (f"<!doctype html>\n<html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
            f"<title>{escape(title)}</title></head>\n<body>\n<h1>{escape(title)}</h1>\n"
            + "\n".join(body) + "\n</body></html>\n")
    return html, report
