from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.rotate_whatsapp_token import subscription_app_ids, update_env_token


def test_subscription_app_ids_supports_meta_response_shapes() -> None:
    payload = {
        "data": [
            {"whatsapp_business_api_data": {"id": "app-1"}},
            {"id": "app-2"},
            {"whatsapp_business_api_data": {}},
        ]
    }

    assert subscription_app_ids(payload) == {"app-1", "app-2"}


def test_update_env_token_replaces_existing_value(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "WHATSAPP_ACCESS_TOKEN=old-token\nWHATSAPP_PHONE_NUMBER_ID=123\n",
        encoding="utf-8",
    )

    update_env_token(env_file, "new-token")

    assert env_file.read_text(encoding="utf-8") == (
        'WHATSAPP_ACCESS_TOKEN="new-token"\nWHATSAPP_PHONE_NUMBER_ID=123\n'
    )


def test_update_env_token_adds_missing_value(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("WHATSAPP_PHONE_NUMBER_ID=123\n", encoding="utf-8")

    update_env_token(env_file, "new-token")

    assert env_file.read_text(encoding="utf-8").endswith(
        'WHATSAPP_ACCESS_TOKEN="new-token"\n'
    )
