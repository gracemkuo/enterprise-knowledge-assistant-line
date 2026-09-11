import hmac
import logging

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from linebot.v3.exceptions import InvalidSignatureError

from .config import Settings, get_settings
from .knowledge import AgentSearchClient
from .line_service import LineKnowledgeService
from .legal_pages import data_deletion_html, privacy_policy_html
from .whatsapp_service import (
    InvalidWhatsAppPayload,
    InvalidWhatsAppSignature,
    WhatsAppKnowledgeService,
)

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Enterprise Knowledge Assistant",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy_policy() -> str:
        return privacy_policy_html()

    @app.get("/data-deletion", response_class=HTMLResponse)
    def data_deletion() -> str:
        return data_deletion_html()

    @app.post("/callback")
    @app.post("/webhooks/line")
    async def callback(request: Request) -> Response:
        signature = request.headers.get("X-Line-Signature")
        if not signature:
            raise HTTPException(status_code=400, detail="Missing LINE signature")

        body = (await request.body()).decode("utf-8")
        runtime_settings = settings or get_settings()
        service = LineKnowledgeService(
            runtime_settings,
            AgentSearchClient(runtime_settings),
        )

        try:
            await run_in_threadpool(service.handle_webhook, body, signature)
        except InvalidSignatureError as exc:
            raise HTTPException(status_code=400, detail="Invalid LINE signature") from exc
        except Exception as exc:
            # Do not log message bodies or retrieved company content.
            logger.exception("Webhook processing failed: %s", type(exc).__name__)
            raise HTTPException(status_code=500, detail="Webhook processing failed") from exc

        return Response(content="OK", media_type="text/plain")

    @app.get("/webhooks/whatsapp")
    def verify_whatsapp_webhook(
        mode: str = Query(default="", alias="hub.mode"),
        verify_token: str = Query(default="", alias="hub.verify_token"),
        challenge: str = Query(default="", alias="hub.challenge"),
    ) -> Response:
        runtime_settings = settings or get_settings()
        if (
            mode != "subscribe"
            or not runtime_settings.whatsapp_verify_token
            or not challenge
            or not hmac.compare_digest(
                verify_token.encode("utf-8"),
                runtime_settings.whatsapp_verify_token.encode("utf-8"),
            )
        ):
            raise HTTPException(status_code=403, detail="Webhook verification failed")
        return Response(content=challenge, media_type="text/plain")

    @app.post("/webhooks/whatsapp")
    async def whatsapp_webhook(request: Request) -> Response:
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing WhatsApp signature")

        runtime_settings = settings or get_settings()
        if not runtime_settings.whatsapp_is_configured:
            raise HTTPException(status_code=503, detail="WhatsApp is not configured")

        body = await request.body()
        service = WhatsAppKnowledgeService(
            runtime_settings,
            AgentSearchClient(runtime_settings),
        )
        try:
            await run_in_threadpool(service.handle_webhook, body, signature)
        except InvalidWhatsAppSignature as exc:
            raise HTTPException(
                status_code=401, detail="Invalid WhatsApp signature"
            ) from exc
        except InvalidWhatsAppPayload as exc:
            raise HTTPException(
                status_code=400, detail="Invalid WhatsApp payload"
            ) from exc
        except Exception as exc:
            # Do not log message bodies or retrieved company content.
            logger.exception(
                "WhatsApp webhook processing failed: %s", type(exc).__name__
            )
            raise HTTPException(
                status_code=500, detail="Webhook processing failed"
            ) from exc

        return Response(content="OK", media_type="text/plain")

    return app


app = create_app()
