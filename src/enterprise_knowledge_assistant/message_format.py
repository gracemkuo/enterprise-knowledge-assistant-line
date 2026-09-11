from __future__ import annotations

from .knowledge import KnowledgeAnswer


def format_knowledge_answer(answer: KnowledgeAnswer, max_chars: int) -> str:
    """Format one Agent Search answer consistently for every chat channel."""

    text = answer.text.strip()
    if answer.sources:
        source_lines = ["", "來源："]
        source_lines.extend(
            f"{index}. {source.title}\n{source.uri}"
            for index, source in enumerate(answer.sources, start=1)
        )
        text += "\n".join(source_lines)

    truncation_notice = "\n（內容已截短）"
    if len(text) > max_chars:
        text = text[: max_chars - len(truncation_notice)].rstrip()
        text += truncation_notice
    return text
