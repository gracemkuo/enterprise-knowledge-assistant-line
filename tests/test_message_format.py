from enterprise_knowledge_assistant.knowledge import KnowledgeAnswer, Source
from enterprise_knowledge_assistant.message_format import format_knowledge_answer


def test_source_footer_survives_answer_truncation() -> None:
    answer = KnowledgeAnswer("內容" * 500, (Source("客戶文件.pdf", "gs://bucket/file.pdf"),))
    text = format_knowledge_answer(answer, 500)
    assert len(text) <= 500
    assert "內容已截短" in text
    assert text.endswith("參考文件（共 1 份）：\n1. 客戶文件.pdf")
    assert "gs://" not in text


def test_format_removes_only_redundant_list_intro_and_source_title():
    answer = KnowledgeAnswer('依據內部QA，說明如下：\n\n* 直接聯繫銀行。\n\n客戶文件', (Source('客戶文件.pdf', 'gs://bucket/file.pdf'),))
    text = format_knowledge_answer(answer, 4000)
    assert text == '* 直接聯繫銀行。\n參考文件（共 1 份）：\n1. 客戶文件.pdf'


def test_format_preserves_dated_qualification():
    answer = KnowledgeAnswer('依2026-01-07內部QA，規定如下：\n\n* 預計兩個月。')
    assert '2026-01-07' in format_knowledge_answer(answer, 4000)
