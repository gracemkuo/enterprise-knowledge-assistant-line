import hashlib
import hmac
import json
from typing import cast

import httpx
import pytest

from enterprise_knowledge_assistant.config import Settings
from enterprise_knowledge_assistant.knowledge import (
    AgentSearchClient,
    KnowledgeAnswer,
    Source,
)
from enterprise_knowledge_assistant.whatsapp_service import (
    InvalidWhatsAppSignature,
    WhatsAppKnowledgeService,
)


class StubKnowledge:
    def __init__(self) -> None:
        self.questions: list[tuple[str, str]] = []

    def ask(self, question: str, user_id: str) -> KnowledgeAnswer:
        self.questions.append((question, user_id))
        return KnowledgeAnswer(
            "共用知識庫答案",
            (Source("公司文件", "https://drive.google.com/example"),),
        )


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "line_channel_secret": "line-secret",
        "line_channel_access_token": "line-token",
        "google_cloud_project": "test-project",
        "agent_search_engine_id": "test-engine",
        "whatsapp_verify_token": "verify-token",
        "whatsapp_app_secret": "app-secret",
        "whatsapp_access_token": "access-token",
        "whatsapp_phone_number_id": "123456789",
        "whatsapp_allowed_phone_numbers": "+971 50 123 4567",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def sign(settings: Settings, body: bytes) -> str:
    digest = hmac.new(
        settings.whatsapp_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def message_body(
    *, sender: str = "971501234567", message_type: str = "text"
) -> bytes:
    message: dict[str, object] = {
        "from": sender,
        "id": "wamid.example",
        "type": message_type,
    }
    if message_type == "text":
        message["text"] = {"body": "之前如何處理客訴？"}

    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "123456789"},
                                "messages": [message],
                            },
                        }
                    ]
                }
            ],
        }
    ).encode()


def make_http_client(sent_payloads: list[dict[str, object]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        sent_payloads.append(json.loads(request.content))
        assert request.url == (
            "https://graph.facebook.com/v26.0/123456789/messages"
        )
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json={"messages": [{"id": "wamid.reply"}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_allowed_whatsapp_users_are_normalized() -> None:
    settings = make_settings(
        whatsapp_allowed_phone_numbers="+971 50 123 4567, +886-912-345-678"
    )

    assert settings.allowed_whatsapp_users == {
        "971501234567",
        "886912345678",
    }


def test_valid_text_message_uses_shared_knowledge_client() -> None:
    settings = make_settings()
    knowledge = StubKnowledge()
    sent_payloads: list[dict[str, object]] = []
    service = WhatsAppKnowledgeService(
        settings,
        cast(AgentSearchClient, knowledge),
        http_client=make_http_client(sent_payloads),
    )
    body = message_body()

    handled = service.handle_webhook(body, sign(settings, body))

    assert handled == 1
    assert knowledge.questions == [
        ("之前如何處理客訴？", "whatsapp:971501234567")
    ]
    assert sent_payloads[0]["to"] == "971501234567"
    assert "共用知識庫答案" in sent_payloads[0]["text"]["body"]  # type: ignore[index]
    assert "公司文件" in sent_payloads[0]["text"]["body"]  # type: ignore[index]


def test_invalid_signature_is_rejected_before_processing() -> None:
    settings = make_settings()
    service = WhatsAppKnowledgeService(
        settings,
        cast(AgentSearchClient, StubKnowledge()),
        http_client=make_http_client([]),
    )

    with pytest.raises(InvalidWhatsAppSignature):
        service.handle_webhook(message_body(), "sha256=not-valid")


def test_unapproved_sender_gets_access_denied_message() -> None:
    settings = make_settings(whatsapp_allowed_phone_numbers="971500000000")
    knowledge = StubKnowledge()
    sent_payloads: list[dict[str, object]] = []
    service = WhatsAppKnowledgeService(
        settings,
        cast(AgentSearchClient, knowledge),
        http_client=make_http_client(sent_payloads),
    )
    body = message_body()

    handled = service.handle_webhook(body, sign(settings, body))

    assert handled == 1
    assert knowledge.questions == []
    assert "尚未取得" in sent_payloads[0]["text"]["body"]  # type: ignore[index]


def test_non_text_message_does_not_query_knowledge() -> None:
    settings = make_settings()
    knowledge = StubKnowledge()
    sent_payloads: list[dict[str, object]] = []
    service = WhatsAppKnowledgeService(
        settings,
        cast(AgentSearchClient, knowledge),
        http_client=make_http_client(sent_payloads),
    )
    body = message_body(message_type="image")

    handled = service.handle_webhook(body, sign(settings, body))

    assert handled == 1
    assert knowledge.questions == []
    assert "僅支援文字" in sent_payloads[0]["text"]["body"]  # type: ignore[index]


def test_status_webhook_is_acknowledged_without_a_reply() -> None:
    settings = make_settings()
    sent_payloads: list[dict[str, object]] = []
    service = WhatsAppKnowledgeService(
        settings,
        cast(AgentSearchClient, StubKnowledge()),
        http_client=make_http_client(sent_payloads),
    )
    body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {"statuses": [{"status": "delivered"}]},
                        }
                    ]
                }
            ],
        }
    ).encode()

    handled = service.handle_webhook(body, sign(settings, body))

    assert handled == 0
    assert sent_payloads == []
