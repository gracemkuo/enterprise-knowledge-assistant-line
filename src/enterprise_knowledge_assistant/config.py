from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    # Keep the legacy adapter available, but use WhatsApp by default.
    line_enabled: bool = False
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_allowed_user_ids: str = ""

    # Empty values allow the knowledge-layer CLI to run without chat credentials.
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
    agent_search_passage_retrieval: bool = False
    # Explicit search params make the Answer API ground on full chunks rather
    # than short extracts; values above 10 are accepted (max 25) but still
    # yield 10 references. The low-relevance filter rejects those chunks, so
    # disable it together with this setting.
    agent_search_max_return_results: int | None = Field(default=None, ge=1, le=25)
    agent_search_ignore_low_relevant_content: bool = True
    # The built-in rephraser searches only its rewrites, never the original
    # question, and can change the meaning of colloquial questions.
    agent_search_disable_query_rephraser: bool = False
    agent_search_answer_preamble: str = (
        "請僅依提供的文件回答問題，使用繁體中文，簡潔且完整。"
        "直接從重點開始，以簡短條列式回答；每點只說明具體答案或必要條件。"
        "不要開場白、重述問題或結尾總結；不要使用「依據提供的文件」、"
        "「根據內部QA文件」、「以下為具體說明」等引介語。"
        "文件名稱由程式在回答底部列出，正文不重複交代來源；"
        "但影響答案的年度、版本、草稿狀態及適用範圍仍須保留。"
        "逐項回答問題要求的內容；找不到的部分明確說明文件未提供，不自行補寫。"
        "保留原文的條件、門檻、年度、例外、草稿或擬答狀態及須依正式合約確認的限制。"
        "維持原文的確定程度：可能、預計、待釐清不得改寫成必然或已確定。"
        "只回答與問題直接相關的內容，不額外延伸未被文件充分支持的稅務或投資結論。"
        "需要多份文件時，分別說明各文件支持的部分，不混淆服務核實與產品審查。"
        "遵循引用標記規則；來源檔名由程式另外顯示，請勿自行編造來源名稱。"
    )
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
