from __future__ import annotations

from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from .config import Settings
from .knowledge import AgentSearchClient, KnowledgeAnswer
from .message_format import format_knowledge_answer


class LineKnowledgeService:
    def __init__(self, settings: Settings, knowledge: AgentSearchClient) -> None:
        self.settings = settings
        self.knowledge = knowledge
        self.parser = WebhookParser(settings.line_channel_secret)
        self.configuration = Configuration(
            access_token=settings.line_channel_access_token
        )

    def handle_webhook(self, body: str, signature: str) -> int:
        events = self.parser.parse(body, signature)
        handled = 0

        for event in events:
            if not isinstance(event, MessageEvent) or not isinstance(
                event.message, TextMessageContent
            ):
                continue

            user_id = getattr(event.source, "user_id", None) or "unknown"
            if user_id not in self.settings.allowed_line_users:
                self._reply(event.reply_token, "此帳號尚未取得知識庫使用權限。")
                handled += 1
                continue

            answer = self.knowledge.ask(event.message.text, f"line:{user_id}")
            self._reply(event.reply_token, self.format_answer(answer))
            handled += 1

        return handled

    def format_answer(self, answer: KnowledgeAnswer) -> str:
        return format_knowledge_answer(
            answer, self.settings.max_line_message_chars
        )

    def _reply(self, reply_token: str, text: str) -> None:
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text)],
                )
            )
