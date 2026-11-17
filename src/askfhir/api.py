"""FastAPI app: POST /ask, GET /docs, GET /healthz, GET / (chat UI).

Run:  PYTHONPATH=src uvicorn askfhir.api:app --port 8000
Set ASKFHIR_FAKE_MODELS=1 to run with the deterministic fake models
(no downloads) — useful for smoke tests; retrieval quality is lexical only.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .observability import get_store
from .service import AskFHIRService

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_INDEX = BASE_DIR / "static" / "index.html"
STATIC_OBSERVABILITY = BASE_DIR / "static" / "observability.html"

_service: AskFHIRService | None = None


def get_service() -> AskFHIRService:
    global _service
    if _service is None:
        fake = os.environ.get("ASKFHIR_FAKE_MODELS") == "1"
        _service = AskFHIRService.load(
            corpus_dir=BASE_DIR / "corpus",
            index_dir=BASE_DIR / "data" / "index",
            fake=fake,
        )
    return _service


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def create_app(service: AskFHIRService | None = None) -> FastAPI:
    # docs_url=None: GET /docs is our corpus listing, not Swagger UI.
    app = FastAPI(title="AskFHIR", version="0.1.0", docs_url=None, redoc_url=None)
    if service is not None:
        global _service
        _service = service

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/docs")
    def docs() -> list[dict]:
        return get_service().docs()

    @app.post("/ask")
    def ask(req: AskRequest) -> JSONResponse:
        result = get_service().ask(req.question)
        return JSONResponse(result)

    @app.get("/observability")
    def observability() -> dict:
        """Latency percentiles, cost per request, and quality signals."""
        return get_store().snapshot()

    @app.get("/observability/traces")
    def traces(limit: int = 20) -> list[dict]:
        return get_store().tracer.recent_traces(limit=min(limit, 100))

    @app.get("/observability/dashboard")
    def observability_dashboard() -> FileResponse:
        return FileResponse(STATIC_OBSERVABILITY, media_type="text/html")

    @app.get("/metrics")
    def metrics() -> PlainTextResponse:
        """Prometheus exposition for scraping."""
        return PlainTextResponse(get_store().prometheus(),
                                 media_type="text/plain")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_INDEX, media_type="text/html")

    return app


app = create_app()
