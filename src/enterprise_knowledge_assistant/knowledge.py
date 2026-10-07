from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any
from urllib.parse import unquote, urlsplit

import google.auth
import httpx
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

from .config import Settings
from .retrieval import retrieve_passages

logger = logging.getLogger("uvicorn.error")


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
        self.last_retrieval_trace: list[dict[str, Any]] = []

    def ask(self, question: str, user_id: str) -> KnowledgeAnswer:
        question = question.strip()
        if not question:
            return KnowledgeAnswer("請輸入想查詢的問題。")

        query_text = self._query_text(question)
        channel = user_id.partition(":")[0] or "unknown"

        credentials = self._credentials
        if credentials is None:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self._credentials = credentials

        if not credentials.valid:
            credentials.refresh(GoogleAuthRequest())

        started = monotonic()
        generation_spec: dict[str, Any] = {
            "includeCitations": True,
            "ignoreLowRelevantContent": True,
            "answerLanguageCode": self.settings.answer_language_code,
        }
        if self.settings.agent_search_answer_preamble.strip():
            generation_spec["promptSpec"] = {
                "preamble": self.settings.agent_search_answer_preamble.strip()
            }
        request_payload: dict[str, Any] = {
            "query": {"text": query_text},
            "userPseudoId": self._pseudonymous_user_id(user_id),
            "answerGenerationSpec": generation_spec,
        }
        self.last_retrieval_trace = []
        if self.settings.agent_search_passage_retrieval:
            def search(query: str) -> dict[str, Any]:
                result = self._http.post(
                    self._answer_endpoint().removesuffix(":answer") + ":search",
                    headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
                    json={"query": query, "pageSize": 10, "contentSearchSpec": {
                        "extractiveContentSpec": {"maxExtractiveSegmentCount": 10,
                                                  "numPreviousSegments": 2, "numNextSegments": 2}
                    }},
                )
                result.raise_for_status()
                return result.json()
            passages, self.last_retrieval_trace = retrieve_passages(query_text, search)
            if passages:
                request_payload["searchSpec"] = {"searchResultList": {"searchResults": passages}}
        response = self._http.post(
            self._answer_endpoint(),
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json=request_payload,
        )
        response.raise_for_status()
        payload = response.json()
        answer = self.parse_answer(payload)
        raw_answer = payload.get("answer") or {}
        skipped_reasons = raw_answer.get("answerSkippedReasons") or []
        logger.info(
            "Agent Search completed channel=%s duration_ms=%d question_chars=%d "
            "context_applied=%s answer_chars=%d source_count=%d skipped_reasons=%s",
            channel,
            int((monotonic() - started) * 1000),
            len(question),
            bool(self.settings.agent_search_query_context.strip()),
            len(answer.text),
            len(answer.sources),
            ",".join(str(reason) for reason in skipped_reasons) or "none",
        )
        return answer

    def _query_text(self, question: str) -> str:
        context = self.settings.agent_search_query_context.strip()
        if not context:
            return question
        return f"{question}\n\n檢索背景：{context}"

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
        references = answer.get("references", [])
        cited_ids = {
            str(source.get("referenceId", ""))
            for citation in answer.get("citations", [])
            for source in citation.get("sources", [])
        }
        for index, reference in enumerate(references):
            if str(index) not in cited_ids:
                continue
            metadata = reference.get("chunkInfo", {}).get("documentMetadata", {})
            if not metadata:
                metadata = reference.get("unstructuredDocumentInfo", {})
            if not metadata:
                metadata = reference.get("structuredDocumentInfo", {})
            uri = str(metadata.get("uri") or "").strip()
            if not uri:
                continue
            filename = unquote(urlsplit(uri).path.rsplit("/", 1)[-1])
            title = filename or str(metadata.get("title") or "來源文件").strip()
            key = (title, uri)
            if key not in seen:
                sources.append(Source(title=title, uri=uri))
                seen.add(key)

        return KnowledgeAnswer(text=text, sources=tuple(sources))
