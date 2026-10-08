import json

import openpyxl

from enterprise_knowledge_assistant.ingestion import run
from enterprise_knowledge_assistant.ingestion.normalize import clean_text
from enterprise_knowledge_assistant.ingestion.pdf import join_lines, table_rows


def word(text, x, y):
    return {"text": text, "x0": x - 1, "x1": x + 1, "top": y - 1, "bottom": y + 1}


def test_table_keeps_each_year_in_its_own_column():
    # Columns at x 0-10-20-30; the label cell spans both rows.
    cells = [(0, 0, 10, 20), (10, 0, 20, 10), (20, 0, 30, 10), (10, 10, 20, 20), (20, 10, 30, 20)]
    words = [word("薪資所得", 5, 10), word("每人最高", 15, 3), word("218,000", 15, 7),
             word("每人最高", 25, 3), word("227,000", 25, 7), word("262,000", 15, 15), word("272,000", 25, 15)]
    rows, unplaced = table_rows(cells, words)
    assert rows == [[("薪資所得", 1), ("每人最高 218,000", 1), ("每人最高 227,000", 1)],
                    [("薪資所得", 1), ("262,000", 1), ("272,000", 1)]]
    assert unplaced == []


def test_table_merges_wide_cell_and_reports_unplaced_words():
    cells = [(0, 0, 10, 10), (10, 0, 30, 10), (0, 10, 10, 20), (10, 10, 20, 20), (20, 10, 30, 20)]
    words = [word("儲蓄投資", 5, 5), word("270,000", 20, 5), word("單身", 5, 15),
             word("131,000", 15, 15), word("136,000", 25, 15), word("註", 50, 5)]
    rows, unplaced = table_rows(cells, words)
    assert rows == [[("儲蓄投資", 1), ("270,000", 2)], [("單身", 1), ("131,000", 1), ("136,000", 1)]]
    assert unplaced == ["註"]


def test_text_cleanup_and_line_joining():
    assert clean_text("六⼤⾯向⻑期\x83") == "六大面向長期"
    assert clean_text("（單位：新臺幣）") == "（單位：新臺幣）"
    assert join_lines(["期待態", "度，2026", "Family CFO", "角色"]) == "期待態度，2026 Family CFO 角色"


def test_pipeline_skips_media_and_duplicates_and_reuses_unchanged(tmp_path):
    source, output = tmp_path / "source", tmp_path / "out"
    (source / "sub").mkdir(parents=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "私人銀行"
    sheet.append(["No", "題目", "回覆", "備註"])
    sheet.append([None, "有哪些利益抵觸？", None, "內部"])
    workbook.save(source / "qa.xlsx")
    (source / "sub" / "copy.xlsx").write_bytes((source / "qa.xlsx").read_bytes())
    (source / "talk.m4a").write_bytes(b"audio")
    (source / "old.doc").write_bytes(b"legacy")
    (source / "notes.txt").write_text("plain")

    first = run(source, output)
    status = {record["path"]: record["status"] for record in first["records"]}
    assert status == {"qa.xlsx": "converted", "sub/copy.xlsx": "duplicate", "talk.m4a": "skipped",
                      "old.doc": "skipped", "notes.txt": "passthrough"}
    html = (output / "documents" / "qa.xlsx.html").read_text()
    assert "私人銀行 第 2 列：有哪些利益抵觸？" in html
    assert "<b>回覆</b>：（空白）" in html and "<b>No</b>" not in html
    assert sorted(path.name for path in (output / "documents").iterdir()) == ["notes.txt", "qa.xlsx.html"]

    second = run(source, output)
    reused = {record["path"] for record in second["records"] if record.get("reused")}
    assert reused == {"qa.xlsx", "notes.txt"}
    assert json.loads((output / "manifest.json").read_text())["summary"] == second["summary"]


def test_pipeline_include_limits_the_run(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("a")
    (source / "b.txt").write_text("b")
    manifest = run(source, tmp_path / "out", include=["b.txt"])
    assert [record["path"] for record in manifest["records"]] == ["b.txt"]


def test_workbook_leaves_out_internal_rows_and_hidden_columns(tmp_path):
    source, output = tmp_path / "source", tmp_path / "out"
    source.mkdir()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["No", "題目", "回覆", "備註"])
    sheet.append([1, "對外問題", "對外回答", "實際諮詢的QA"])
    sheet.append([2, "內部問題", "主推海外債券", "內部"])
    sheet.append([3, "未定問題", "初步回答", "待與主管確認"])
    workbook.save(source / "qa.xlsx")
    options = {"exclude_columns": ["備註"], "exclude_row_markers": ["內部"]}

    manifest = run(source, output, **options)
    html = (output / "documents" / "qa.xlsx.html").read_text()
    assert "對外回答" in html and "主推海外債券" not in html
    assert "備註" not in html and "實際諮詢的QA" not in html and "待與主管確認" not in html
    assert html.count("此題內容尚待確認") == 1
    assert manifest["records"][0]["details"]["excluded_rows"] == 1
    assert run(source, output, **options)["records"][0].get("reused")
    assert not run(source, output)["records"][0].get("reused")


def test_prune_removes_outputs_without_a_source(tmp_path):
    source, output = tmp_path / "source", tmp_path / "out"
    source.mkdir()
    (source / "a.txt").write_text("a")
    run(source, output)
    (source / "a.txt").unlink()
    assert run(source, output)["stale_outputs"] == ["a.txt"]
    assert run(source, output, prune=True)["stale_outputs"] == []
    assert list((output / "documents").iterdir()) == []
