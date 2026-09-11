import json

from google.auth.credentials import Credentials
import httpx

from enterprise_knowledge_assistant.config import Settings
from enterprise_knowledge_assistant.knowledge import AgentSearchClient


class StaticCredentials(Credentials):
    def __init__(self) -> None:
        super().__init__()
        self.token = "test-google-token"

    def refresh(self, request: object) -> None:
        self.token = "test-google-token"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "line_channel_secret": "line-secret",
        "line_channel_access_token": "line-token",
        "google_cloud_project": "test-project",
        "agent_search_engine_id": "test-engine",
        "agent_search_query_context": "",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_parse_answer_extracts_unique_sources() -> None:
    payload = {
        "answer": {
            "answerText": "The team chose a preview step.",
            "references": [
                {
                    "chunkInfo": {
                        "documentMetadata": {
                            "title": "Issue Retrospective",
                            "uri": "https://drive.google.com/example",
                        }
                    }
                },
                {
                    "chunkInfo": {
                        "documentMetadata": {
                            "title": "Issue Retrospective",
                            "uri": "https://drive.google.com/example",
                        }
                    }
                },
            ],
        }
    }

    answer = AgentSearchClient.parse_answer(payload)

    assert answer.text == "The team chose a preview step."
    assert len(answer.sources) == 1
    assert answer.sources[0].title == "Issue Retrospective"


def test_parse_answer_uses_safe_no_answer_message() -> None:
    answer = AgentSearchClient.parse_answer({"answer": {}})

    assert "找不到足夠資料" in answer.text
    assert answer.sources == ()


def test_parse_answer_supports_unstructured_document_reference() -> None:
    payload = {
        "answer": {
            "answerText": "A sourced answer.",
            "references": [
                {
                    "unstructuredDocumentInfo": {
                        "title": "Workspace document",
                        "uri": "https://drive.google.com/unstructured-example",
                    }
                }
            ],
        }
    }

    answer = AgentSearchClient.parse_answer(payload)

    assert answer.sources[0].title == "Workspace document"
    assert answer.sources[0].uri.endswith("unstructured-example")


def test_pseudonymous_id_does_not_expose_line_user_id() -> None:
    user_id = "U-real-line-user-id"

    pseudonymous_id = AgentSearchClient._pseudonymous_user_id(user_id)

    assert user_id not in pseudonymous_id
    assert len(pseudonymous_id) == 64


def test_query_context_is_appended_without_changing_the_user_question() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"answer": {"answerText": "摘要"}})

    client = AgentSearchClient(
        make_settings(
            agent_search_query_context=(
                "知識庫包含使用者本人的履歷；問題中的「我」指履歷本人。"
            )
        ),
        credentials=StaticCredentials(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.ask("請總結我的履歷", "whatsapp:masked-user")

    assert requests[0]["query"]["text"] == (  # type: ignore[index]
        "請總結我的履歷\n\n檢索背景："
        "知識庫包含使用者本人的履歷；問題中的「我」指履歷本人。"
    )
    assert requests[0]["answerGenerationSpec"][  # type: ignore[index]
        "ignoreLowRelevantContent"
    ] is True


def test_query_is_unchanged_when_context_is_empty() -> None:
    client = AgentSearchClient(make_settings())

    assert client._query_text("原始問題") == "原始問題"
