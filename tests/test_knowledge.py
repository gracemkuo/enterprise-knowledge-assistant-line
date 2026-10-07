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
            "citations": [{"sources": [{"referenceId": "0"}, {"referenceId": "1"}]}],
            "references": [
                {
                    "chunkInfo": {
                        "documentMetadata": {
                            "title": "Issue Retrospective",
                            "uri": "gs://test-bucket/Issue%20Retrospective.pdf",
                        }
                    }
                },
                {
                    "chunkInfo": {
                        "documentMetadata": {
                            "title": "Issue Retrospective",
                            "uri": "gs://test-bucket/Issue%20Retrospective.pdf",
                        }
                    }
                },
            ],
        }
    }

    answer = AgentSearchClient.parse_answer(payload)

    assert answer.text == "The team chose a preview step."
    assert len(answer.sources) == 1
    assert answer.sources[0].title == "Issue Retrospective.pdf"


def test_parse_answer_uses_safe_no_answer_message() -> None:
    answer = AgentSearchClient.parse_answer({"answer": {}})

    assert "找不到足夠資料" in answer.text
    assert answer.sources == ()


def test_parse_answer_supports_unstructured_document_reference() -> None:
    payload = {
        "answer": {
            "answerText": "A sourced answer.",
            "citations": [{"sources": [{"referenceId": "0"}]}],
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

    assert answer.sources[0].title == "unstructured-example"
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
                "本次查詢以客戶提供的文件版本為準。"
            )
        ),
        credentials=StaticCredentials(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.ask("請總結文件中的服務流程", "whatsapp:masked-user")

    assert requests[0]["query"]["text"] == (  # type: ignore[index]
        "請總結文件中的服務流程\n\n檢索背景："
        "本次查詢以客戶提供的文件版本為準。"
    )
    assert requests[0]["answerGenerationSpec"][  # type: ignore[index]
        "ignoreLowRelevantContent"
    ] is True
    assert requests[0]["answerGenerationSpec"]["promptSpec"]["preamble"] == (  # type: ignore[index]
        client.settings.agent_search_answer_preamble
    )


def test_parse_answer_excludes_uncited_search_references() -> None:
    payload = {"answer": {
        "answerText": "回答",
        "citations": [{"sources": [{"referenceId": "1"}]}],
        "references": [
            {"unstructuredDocumentInfo": {"uri": "gs://bucket/uncited.pdf"}},
            {"unstructuredDocumentInfo": {"uri": "gs://bucket/cited.pdf"}},
        ],
    }}
    answer = AgentSearchClient.parse_answer(payload)
    assert [s.title for s in answer.sources] == ["cited.pdf"]


def test_query_is_unchanged_when_context_is_empty() -> None:
    client = AgentSearchClient(make_settings())

    assert client._query_text("原始問題") == "原始問題"


def test_passage_mode_sends_original_segments_with_source_identity() -> None:
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path.endswith(':search'):
            return httpx.Response(200, json={'results': [{'document': {
                'name': 'projects/test/documents/one',
                'derivedStructData': {'link': 'gs://bucket/customer.pdf', 'title': '客戶文件',
                                      'extractive_segments': [{'content': '客戶文件的原文', 'pageNumber': '5'}]},
            }}]})
        return httpx.Response(200, json={'answer': {'answerText': '回答'}})
    client = AgentSearchClient(
        make_settings(agent_search_passage_retrieval=True), credentials=StaticCredentials(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.ask('請解釋客戶文件', 'benchmark:test')
    assert len(requests) == 2
    info = requests[-1][1]['searchSpec']['searchResultList']['searchResults'][0]['unstructuredDocumentInfo']
    assert info['documentContexts'] == [{'content': '客戶文件的原文', 'pageIdentifier': '5'}]
    assert info['uri'] == 'gs://bucket/customer.pdf'
    assert requests[-1][1]['query']['text'] == '請解釋客戶文件'
