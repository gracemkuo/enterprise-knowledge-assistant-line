from enterprise_knowledge_assistant.knowledge import AgentSearchClient


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
