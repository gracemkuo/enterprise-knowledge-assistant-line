from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import google.auth
import httpx
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

from .config import Settings


@dataclass(frozen=True)
class Source:
    title: str
    uri: str


@dataclass(frozen=True)
class KnowledgeAnswer:
    text: str
    sources: tuple[Source, ...] = ()


class AgentSearchClient:
    """Thin client for Google Agent Search's managed answer API.

    The portfolio POC uses a Cloud Storage-backed data store. Customer
    deployments can replace the source without changing this API boundary.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        credentials: Credentials | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._credentials = credentials
        self._http = http_client or httpx.Client(timeout=45.0)

    def ask(self, question: str, user_id: str) -> KnowledgeAnswer:
        question = question.strip()
        if not question:
            return KnowledgeAnswer("請輸入想查詢的問題。")

        credentials = self._credentials
        if credentials is None:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self._credentials = credentials

        if not credentials.valid:
            credentials.refresh(GoogleAuthRequest())

        response = self._http.post(
            self._answer_endpoint(),
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json={
                "query": {"text": question},
                "userPseudoId": self._pseudonymous_user_id(user_id),
                "answerGenerationSpec": {
                    "includeCitations": True,
                    "ignoreLowRelevantContent": True,
                    "answerLanguageCode": self.settings.answer_language_code,
                },
            },
        )
        response.raise_for_status()
        return self.parse_answer(response.json())

    def _answer_endpoint(self) -> str:
        location = self.settings.agent_search_location
        host = (
            "discoveryengine.googleapis.com"
            if location == "global"
            else f"{location}-discoveryengine.googleapis.com"
        )
        project = self.settings.google_cloud_project
        engine = self.settings.agent_search_engine_id
        return (
            f"https://{host}/v1/projects/{project}/locations/{location}/"
            "collections/default_collection/engines/"
            f"{engine}/servingConfigs/default_search:answer"
        )

    @staticmethod
    def _pseudonymous_user_id(user_id: str) -> str:
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()

    @staticmethod
    def parse_answer(payload: dict[str, Any]) -> KnowledgeAnswer:
        answer = payload.get("answer", {})
        text = str(answer.get("answerText", "")).strip()
        if not text:
            text = "目前知識庫中找不到足夠資料回答這個問題。"

        sources: list[Source] = []
        seen: set[tuple[str, str]] = set()
        for reference in answer.get("references", []):
            metadata = reference.get("chunkInfo", {}).get("documentMetadata", {})
            if not metadata:
                metadata = reference.get("unstructuredDocumentInfo", {})
            if not metadata:
                metadata = reference.get("structuredDocumentInfo", {})
            title = str(metadata.get("title") or "來源文件").strip()
            uri = str(metadata.get("uri") or "").strip()
            if not uri:
                continue
            key = (title, uri)
            if key not in seen:
                sources.append(Source(title=title, uri=uri))
                seen.add(key)

        return KnowledgeAnswer(text=text, sources=tuple(sources[:3]))
