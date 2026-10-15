"""Filter, de-duplicate and convert source files into a search-ready folder.

Source files are only read. The output folder holds what may be imported, and
manifest.json records what happened to every source file and why.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .normalize import replace_terms, term_pattern
from .pdf import convert_pdf
from .spreadsheet import convert_workbook

# Bump when conversion output changes so unchanged sources are processed again.
PIPELINE_VERSION = "4"
# Covers and section dividers are normal; flag a file only when many pages lack text.
LOW_TEXT_REVIEW_SHARE = 0.2
MEDIA = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".wma",
         ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wmv", ".webm"}
PASSTHROUGH = {".docx", ".pptx", ".html", ".htm", ".txt"}
NEEDS_CONVERSION = {".doc", ".ppt", ".xls"}
IGNORED_NAMES = {".DS_Store", "README.md", "Thumbs.db"}
DOCUMENTS = "documents"
OFFICE_XML = {".docx", ".pptx"}
TEXT_PASSTHROUGH = {".html", ".htm", ".txt"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_office_with_replacements(path: Path, target: Path, replacements: Sequence[tuple[str, str]]) -> list[str]:
    """Copy a .docx/.pptx, replacing terms inside its XML parts.

    Returns the terms still visible afterwards, e.g. when Word split one word
    across differently formatted runs.
    """

    left: set[str] = set()
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as copy:
        for item in source.infolist():
            data = source.read(item)
            if item.filename.endswith(".xml"):
                xml = replace_terms(data.decode("utf-8", errors="replace"), replacements)
                text = re.sub(r"<[^>]+>", "", xml)
                left.update(old for old, _ in replacements if term_pattern(old).search(text))
                data = xml.encode("utf-8")
            copy.writestr(item, data)
    return sorted(left)


def run(
    source: Path,
    output: Path,
    *,
    include: Iterable[str] | None = None,
    exclude_columns: Sequence[str] = (),
    exclude_row_markers: Sequence[str] = (),
    prune: bool = False,
    replacements: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Process `source` into `output` and return the manifest.

    `include` limits the run to these paths relative to `source`. The two
    exclude options apply to workbooks. `prune` deletes files in the output
    folder that no source file produces any more. `replacements` lists
    (old, new) terms rewritten in every published document and file name.
    """

    source, output = source.resolve(), output.resolve()
    documents = output / DOCUMENTS
    documents.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    options = {"exclude_columns": sorted(exclude_columns), "exclude_row_markers": sorted(exclude_row_markers),
               "replacements": [list(pair) for pair in replacements]}
    previous: dict[str, dict[str, Any]] = {}
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if old.get("pipeline_version") == PIPELINE_VERSION and old.get("options") == options:
            previous = {r["sha256"]: r for r in old["records"] if r.get("output")}

    wanted = set(include) if include is not None else None
    paths = sorted(p for p in source.rglob("*")
                   if p.is_file() and p.name not in IGNORED_NAMES and not p.name.startswith("._"))
    records: list[dict[str, Any]] = []
    first_seen: dict[str, str] = {}
    used_names: set[str] = set()
    for path in paths:
        relative = path.relative_to(source).as_posix()
        if wanted is not None and relative not in wanted:
            continue
        suffix = path.suffix.lower()
        record: dict[str, Any] = {"path": relative, "type": suffix, "bytes": path.stat().st_size}
        records.append(record)
        if suffix in MEDIA:
            record.update(status="skipped", reason="影音檔，第一階段不處理")
            continue
        digest = record["sha256"] = _sha256(path)
        if digest in first_seen:
            record.update(status="duplicate", reason="內容與另一檔完全相同", duplicate_of=first_seen[digest])
            continue
        first_seen[digest] = relative
        if suffix in NEEDS_CONVERSION:
            record.update(status="skipped", reason="舊版 Office 格式，需先轉成新版格式")
            continue
        if suffix not in PASSTHROUGH | {".pdf", ".xlsx"}:
            record.update(status="skipped", reason="不支援的格式")
            continue

        earlier = previous.get(digest)
        if earlier and (documents / earlier["output"]).exists() and earlier["output"] not in used_names:
            record.update({key: earlier[key] for key in ("status", "reason", "output", "details") if key in earlier})
            record["reused"] = True
            used_names.add(record["output"])
            continue

        html: str | None = None
        details: dict[str, Any] = {}
        if suffix == ".pdf":
            html, details = convert_pdf(path, path.name)
        elif suffix == ".xlsx":
            html, details = convert_workbook(path, path.name, exclude_columns=exclude_columns,
                                             exclude_row_markers=exclude_row_markers)
        # Keep the original name inside the published one so answers can cite it.
        name = replace_terms(path.name, replacements)
        if name in used_names or f"{name}.html" in used_names:
            name = replace_terms(f"{path.stem}-{digest[:8]}{path.suffix}", replacements)
        if html is not None:
            name += ".html"
        used_names.add(name)
        if html is not None:
            (documents / name).write_text(replace_terms(html, replacements), encoding="utf-8")
            review = []
            if len(details.get("low_text_pages", [])) > LOW_TEXT_REVIEW_SHARE * details.get("pages", 1):
                review.append("部分頁面幾乎沒有文字，圖片內容可能未納入")
            if details.get("table_pages_with_unplaced_words"):
                review.append("部分表格有文字未能放入儲存格，已附在表格後，順序需抽查")
            record.update(status="needs_review" if review else "converted",
                          reason="；".join(review) or "已由原始文字層轉換", output=name, details=details)
        else:
            review = []
            if suffix == ".pdf":
                shutil.copyfile(path, documents / name)
                review.append("PDF 沒有可用文字層，原檔交由搜尋服務辨識")
                if replacements:
                    review.append("圖片中的字詞無法自動替換，需人工確認")
            elif replacements and suffix in TEXT_PASSTHROUGH:
                text = path.read_text(encoding="utf-8", errors="replace")
                (documents / name).write_text(replace_terms(text, replacements), encoding="utf-8")
            elif replacements and suffix in OFFICE_XML:
                left = _copy_office_with_replacements(path, documents / name, replacements)
                if left:
                    review.append(f"仍含有「{'、'.join(left)}」（可能被格式拆開），需人工修改")
            else:
                shutil.copyfile(path, documents / name)
            record.update(status="needs_review" if review else "passthrough",
                          reason="；".join(review) or "原檔直接使用", output=name, details=details)

    stale = sorted(p.name for p in documents.iterdir() if p.is_file() and p.name not in used_names)
    if prune:
        for name in stale:
            (documents / name).unlink()
        stale = []
    summary: dict[str, int] = {}
    for record in records:
        summary[record["status"]] = summary.get(record["status"], 0) + 1
    manifest = {"pipeline_version": PIPELINE_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_root": str(source), "options": options, "summary": summary,
                "stale_outputs": stale, "records": records}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
