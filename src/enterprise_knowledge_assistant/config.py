from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    line_channel_secret: str = Field(min_length=1)
    line_channel_access_token: str = Field(min_length=1)
    line_allowed_user_ids: str = ""

    # WhatsApp is optional so the existing LINE-only deployment can continue
    # running while Meta Business assets are being prepared.
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    meta_app_id: str = ""
    whatsapp_allowed_phone_numbers: str = ""
    whatsapp_graph_api_version: str = Field(
        default="v26.0", pattern=r"^v\d+\.\d+$"
    )

    google_cloud_project: str = Field(min_length=1)
    agent_search_location: str = "global"
    agent_search_engine_id: str = Field(min_length=1)
    agent_search_query_context: str = ""
    answer_language_code: str = "zh-TW"

    max_line_message_chars: int = Field(default=4500, ge=500, le=5000)
    max_whatsapp_message_chars: int = Field(default=4000, ge=500, le=4096)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_line_users(self) -> set[str]:
        return {
            user_id.strip()
            for user_id in self.line_allowed_user_ids.split(",")
            if user_id.strip()
        }

    @property
    def allowed_whatsapp_users(self) -> set[str]:
        return {
            normalized
            for value in self.whatsapp_allowed_phone_numbers.split(",")
            if (normalized := self.normalize_phone_number(value))
        }

    @property
    def whatsapp_is_configured(self) -> bool:
        return all(
            (
                self.whatsapp_verify_token,
                self.whatsapp_app_secret,
                self.whatsapp_access_token,
                self.whatsapp_phone_number_id,
            )
        )

    @staticmethod
    def normalize_phone_number(value: str) -> str:
        """Return the digits-only WhatsApp identifier used by Cloud API."""

        return "".join(character for character in value if character.isdigit())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
