from fastapi.testclient import TestClient
import pytest

from enterprise_knowledge_assistant.app import create_app
from enterprise_knowledge_assistant.config import Settings


def make_settings() -> Settings:
    return Settings(
        line_channel_secret="line-secret",
        line_channel_access_token="line-token",
        google_cloud_project="test-project",
        agent_search_engine_id="test-engine",
        whatsapp_verify_token="verify-token",
        whatsapp_app_secret="app-secret",
        whatsapp_access_token="access-token",
        whatsapp_phone_number_id="123456789",
    )


def test_health_check_does_not_require_credentials() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_privacy_policy_is_public_and_links_to_data_deletion() -> None:
    client = TestClient(create_app())

    response = client.get("/privacy")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "隱私權政策" in response.text
    assert "eating1210kg@gmail.com" in response.text
    assert 'href="/data-deletion"' in response.text


def test_data_deletion_instructions_are_public() -> None:
    client = TestClient(create_app())

    response = client.get("/data-deletion")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "使用者資料刪除說明" in response.text
    assert "eating1210kg@gmail.com" in response.text


@pytest.mark.parametrize("path", ["/callback", "/webhooks/line"])
def test_line_webhooks_are_disabled_by_default(path: str) -> None:
    client = TestClient(create_app(make_settings()))

    response = client.post(
        path, content=b"{}", headers={"X-Line-Signature": "legacy-signature"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "LINE is disabled"


def test_whatsapp_settings_do_not_require_line_credentials() -> None:
    settings = Settings(
        _env_file=None,
        google_cloud_project="test-project",
        agent_search_engine_id="test-engine",
        whatsapp_verify_token="verify-token",
        whatsapp_app_secret="app-secret",
        whatsapp_access_token="access-token",
        whatsapp_phone_number_id="123456789",
    )

    assert settings.line_enabled is False
    assert settings.line_channel_secret == ""
    assert settings.line_channel_access_token == ""
    assert settings.whatsapp_is_configured is True


def test_callback_requires_line_signature_when_enabled() -> None:
    settings = make_settings().model_copy(update={"line_enabled": True})
    client = TestClient(create_app(settings))

    response = client.post("/callback", content=b"{}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing LINE signature"


def test_enabled_line_without_credentials_is_unavailable() -> None:
    settings = make_settings().model_copy(
        update={"line_enabled": True, "line_channel_secret": ""}
    )
    client = TestClient(create_app(settings))

    response = client.post("/webhooks/line", content=b"{}")

    assert response.status_code == 503
    assert response.json()["detail"] == "LINE is not configured"


def test_whatsapp_webhook_verification_returns_meta_challenge() -> None:
    client = TestClient(create_app(make_settings()))

    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-token",
            "hub.challenge": "challenge-value",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-value"


def test_whatsapp_webhook_verification_rejects_wrong_token() -> None:
    client = TestClient(create_app(make_settings()))

    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge-value",
        },
    )

    assert response.status_code == 403


def test_whatsapp_webhook_requires_signature() -> None:
    client = TestClient(create_app(make_settings()))

    response = client.post("/webhooks/whatsapp", content=b"{}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing WhatsApp signature"


def test_whatsapp_webhook_rejects_invalid_signature() -> None:
    client = TestClient(create_app(make_settings()))

    response = client.post(
        "/webhooks/whatsapp",
        content=b"{}",
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid WhatsApp signature"
