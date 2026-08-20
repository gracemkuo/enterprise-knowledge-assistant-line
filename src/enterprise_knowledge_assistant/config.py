from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    line_channel_secret: str = Field(min_length=1)
    line_channel_access_token: str = Field(min_length=1)
    line_allowed_user_ids: str = ""

    google_cloud_project: str = Field(min_length=1)
    agent_search_location: str = "global"
    agent_search_engine_id: str = Field(min_length=1)
    answer_language_code: str = "zh-TW"

    max_line_message_chars: int = Field(default=4500, ge=500, le=5000)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

