from __future__ import annotations

import re

from .knowledge import KnowledgeAnswer


def _without_intro_and_duplicate_sources(answer: KnowledgeAnswer) -> str:
    text = answer.text.strip()
    lines = text.splitlines()
    # Drop a redundant lead-in only when the next paragraph is already a list.
    # Keep dates and other substantive qualifications in the answer.
    if lines and re.search(r'(?:如下|詳細情況如下)[：:]$', lines[0]) and not re.search(r'\d', lines[0]):
        next_line = next((line.strip() for line in lines[1:] if line.strip()), '')
        if next_line.startswith(('* ', '- ', '1.')):
            lines = lines[1:]
    source_names = {s.title for s in answer.sources} | {s.title.rsplit('.', 1)[0] for s in answer.sources}
    normalized_names = {name.replace('臺', '台') for name in source_names}
    while lines and (not lines[-1].strip() or lines[-1].strip().replace('臺', '台') in normalized_names):
        lines.pop()
    return '\n'.join(lines).strip()


def format_knowledge_answer(answer: KnowledgeAnswer, max_chars: int) -> str:
    """Format one Agent Search answer consistently for every chat channel."""

    text = _without_intro_and_duplicate_sources(answer)
    footer = ""
    if answer.sources:
        source_lines = ["", "引用文件："]
        source_lines.extend(
            f"{index}. {source.title}"
            for index, source in enumerate(answer.sources, start=1)
        )
        footer = "\n".join(source_lines)

    truncation_notice = "\n（內容已截短）"
    available = max_chars - len(footer)
    if len(text) > available:
        text = text[: max(0, available - len(truncation_notice))].rstrip()
        text += truncation_notice
    return (text + footer)[:max_chars]
