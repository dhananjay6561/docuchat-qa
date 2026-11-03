"""FastAPI entrypoint. `create_app` is a factory so tests can build an app with their own settings."""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from app.chat_service import ChatService, Prompt
from app.config import ROOT_DIR, Settings, get_settings
from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.factory import build_provider
from app.logging_db import ChatLogger
from app.memory import SessionMemory
from app.rag.loader import load_chunks
from app.rag.retriever import BM25Retriever
from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.tools.orders import OrderTool

STATIC_DIR = ROOT_DIR / "app" / "static"
# auto_error=False: the check below decides, so an unset API_KEY leaves the API open for local use.
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def build_service(settings: Settings, llm: LLMProvider | None = None) -> ChatService:
    chunks = load_chunks(settings.docs_dir, settings.chunk_words)
    return ChatService(
        llm=llm or build_provider(settings),
        retriever=BM25Retriever(chunks),
        memory=SessionMemory(settings.max_history_turns),
        tools=OrderTool(settings.db_path, settings.tool_failure_mode, settings.tool_timeout_seconds),
        logger=ChatLogger(settings.db_path, settings.input_cost_per_mtok, settings.output_cost_per_mtok),
        prompt=Prompt.load(settings.prompt_file),
        top_k=settings.retrieval_top_k,
        published_emails=frozenset(e.lower() for e in settings.published_emails),
    )


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Built at startup, not import time, so importing the module (e.g. to export the
        # OpenAPI spec) never needs an API key or a database.
        app.state.service = build_service(settings, llm)
        yield

    app = FastAPI(
        title="DocuChat QA",
        version="0.1.0",
        description="Document Q&A assistant with citations, refusals and an order-status tool.",
        lifespan=lifespan,
    )

    def require_api_key(key: str | None = Depends(API_KEY_HEADER)) -> None:
        if not settings.api_key:
            return
        # compare_digest takes the same time for any wrong key, so timing doesn't leak the key.
        if key is None or not secrets.compare_digest(key, settings.api_key):
            raise HTTPException(status_code=401, detail="Missing or invalid API key")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(request: Request) -> HealthResponse:
        service: ChatService = request.app.state.service
        return HealthResponse(
            status="ok", provider=service.llm.name, chunks_indexed=len(service.retriever.chunks)
        )

    @app.post(
        "/chat",
        response_model=ChatResponse,
        tags=["chat"],
        responses={
            400: {"description": "Body could not be decoded (e.g. invalid UTF-8)"},
            401: {"description": "Missing or invalid API key (only when API_KEY is set)"},
            503: {"description": "LLM provider unavailable"},
        },
        dependencies=[Depends(require_api_key)],
    )
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        # Sync endpoint on purpose: FastAPI runs it in a thread pool, so the blocking LLM call
        # doesn't stall other requests.
        service: ChatService = request.app.state.service
        try:
            return service.chat(body.session_id, body.message)
        except LLMUnavailableError as exc:
            raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc

    return app


app = create_app()
