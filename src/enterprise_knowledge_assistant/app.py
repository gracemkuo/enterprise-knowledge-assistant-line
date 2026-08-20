import logging

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from linebot.v3.exceptions import InvalidSignatureError

from .config import Settings, get_settings
from .knowledge import AgentSearchClient
from .line_service import LineKnowledgeService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Enterprise Knowledge Assistant",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/callback")
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

    return app


app = create_app()

