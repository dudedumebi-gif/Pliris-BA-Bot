from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from pliris.config.settings import get_settings
from pliris.database.postgres import close_postgres_pool


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage process-level resources."""

    yield
    close_postgres_pool()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the Pliris BA Bot agentic RAG application.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }
