from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from .config import Settings
from .knowledge import AgentSearchClient, KnowledgeAnswer
from .message_format import format_knowledge_answer

logger = logging.getLogger("uvicorn.error")


class InvalidWhatsAppSignature(ValueError):
    """Raised when a webhook was not signed by the configured Meta app."""


class InvalidWhatsAppPayload(ValueError):
    """Raised when a signed webhook body is not valid JSON."""


class WhatsAppKnowledgeService:
    def __init__(
        self,
        settings: Settings,
        knowledge: AgentSearchClient,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.knowledge = knowledge
        self._http = http_client or httpx.Client(timeout=30.0)

    def handle_webhook(self, body: bytes, signature: str) -> int:
        self.verify_signature(body, signature)
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidWhatsAppPayload("Invalid webhook JSON") from exc

        handled = 0
        inbound_messages = 0
        status_updates = 0
        for value in self._message_values(payload):
            statuses = value.get("statuses") or []
            if isinstance(statuses, list):
                status_updates += len(statuses)

            metadata = value.get("metadata") or {}
            if not isinstance(metadata, dict):
                continue
            phone_number_id = str(metadata.get("phone_number_id") or "")
            if (
                phone_number_id
                and phone_number_id != self.settings.whatsapp_phone_number_id
            ):
                logger.warning(
                    "WhatsApp webhook ignored because Phone Number ID did not match"
                )
                continue

            messages = value.get("messages") or []
            if not isinstance(messages, list):
                continue
            for message in messages:
                if not isinstance(message, dict):
                    continue

                inbound_messages += 1
                event_id = self._event_id(message)

                sender = self.settings.normalize_phone_number(
                    str(message.get("from") or "")
                )
                if not sender:
                    logger.warning(
                        "WhatsApp message ignored event=%s reason=missing_sender",
                        event_id,
                    )
                    continue

                if sender not in self.settings.allowed_whatsapp_users:
                    logger.info(
                        "WhatsApp sender rejected event=%s sender_allowed=false",
                        event_id,
                    )
                    self._send_text(
                        sender,
                        "此 WhatsApp 帳號尚未取得知識庫使用權限。",
                        event_id=event_id,
                    )
                    handled += 1
                    continue

                text = self._text_body(message)
                if text is None:
                    logger.info(
                        "WhatsApp non-text message event=%s sender_allowed=true type=%s",
                        event_id,
                        str(message.get("type") or "unknown"),
                    )
                    self._send_text(
                        sender, "目前僅支援文字問題。", event_id=event_id
                    )
                    handled += 1
                    continue

                logger.info(
                    "WhatsApp text received event=%s sender_allowed=true chars=%d",
                    event_id,
                    len(text),
                )
                answer = self.knowledge.ask(text, f"whatsapp:{sender}")
                self._send_text(
                    sender, self.format_answer(answer), event_id=event_id
                )
                handled += 1

        logger.info(
            "WhatsApp webhook processed inbound_messages=%d status_updates=%d "
            "handled=%d",
            inbound_messages,
            status_updates,
            handled,
        )
        return handled

    def verify_signature(self, body: bytes, signature: str) -> None:
        expected = "sha256=" + hmac.new(
            self.settings.whatsapp_app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise InvalidWhatsAppSignature("Invalid WhatsApp signature")

    def format_answer(self, answer: KnowledgeAnswer) -> str:
        return format_knowledge_answer(
            answer, self.settings.max_whatsapp_message_chars
        )

    @staticmethod
    def _message_values(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        if payload.get("object") != "whatsapp_business_account":
            return []

        values: list[dict[str, Any]] = []
        for entry in payload.get("entry") or []:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes") or []:
                if not isinstance(change, dict) or change.get("field") != "messages":
                    continue
                value = change.get("value")
                if isinstance(value, dict):
                    values.append(value)
        return values

    @staticmethod
    def _text_body(message: dict[str, Any]) -> str | None:
        if message.get("type") != "text":
            return None
        text = message.get("text")
        if not isinstance(text, dict):
            return None
        body = str(text.get("body") or "").strip()
        return body or None

    @staticmethod
    def _event_id(message: dict[str, Any]) -> str:
        message_id = str(message.get("id") or "missing")
        return hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:12]

    def _send_text(
        self, recipient: str, text: str, *, event_id: str = "unknown"
    ) -> None:
        response = self._http.post(
            (
                f"https://graph.facebook.com/"
                f"{self.settings.whatsapp_graph_api_version}/"
                f"{self.settings.whatsapp_phone_number_id}/messages"
            ),
            headers={
                "Authorization": f"Bearer {self.settings.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            },
        )
        response.raise_for_status()
        logger.info(
            "WhatsApp reply sent event=%s status_code=%d chars=%d",
            event_id,
            response.status_code,
            len(text),
        )
