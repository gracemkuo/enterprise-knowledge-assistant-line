from fastapi.testclient import TestClient

from enterprise_knowledge_assistant.app import create_app


def test_health_check_does_not_require_credentials() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_callback_requires_line_signature() -> None:
    client = TestClient(create_app())

    response = client.post("/callback", content=b"{}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing LINE signature"

