from typing import cast

from enterprise_knowledge_assistant.config import Settings
from enterprise_knowledge_assistant.knowledge import (
    AgentSearchClient,
    KnowledgeAnswer,
    Source,
)
from enterprise_knowledge_assistant.line_service import LineKnowledgeService


def make_settings(max_chars: int = 4500) -> Settings:
    return Settings(
        line_channel_secret="test-secret",
        line_channel_access_token="test-token",
        line_allowed_user_ids="U123,U456",
        google_cloud_project="test-project",
        agent_search_engine_id="test-engine",
        max_line_message_chars=max_chars,
    )


def test_allowed_line_users_are_parsed() -> None:
    assert make_settings().allowed_line_users == {"U123", "U456"}


def test_format_answer_adds_sources() -> None:
    service = LineKnowledgeService(
        make_settings(), cast(AgentSearchClient, object())
    )
    answer = KnowledgeAnswer(
        "A grounded answer.",
        (Source("Decision record", "https://drive.google.com/example"),),
    )

    text = service.format_answer(answer)

    assert "A grounded answer." in text
    assert "來源：" in text
    assert "Decision record" in text
    assert "https://drive.google.com/example" in text


def test_format_answer_respects_line_limit() -> None:
    service = LineKnowledgeService(
        make_settings(max_chars=500), cast(AgentSearchClient, object())
    )

    text = service.format_answer(KnowledgeAnswer("x" * 1000))

    assert len(text) <= 500
    assert text.endswith("（內容已截短）")

