"""GET /health — liveness/readiness check for ChromaDB and Ollama dependencies."""

from __future__ import annotations

from fastapi import APIRouter

from .config import settings
from .schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Best-effort dependency check. Never raises — always returns 200 with a
    status field, so it's safe to use as a container/load-balancer probe.
    Use this to quickly see whether ChromaDB and Ollama are reachable
    before hitting /generate-answer.
    """
    chromadb_status = _check_chromadb()
    ollama_status = _check_ollama()

    overall = "ok" if chromadb_status == "ok" and ollama_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        chromadb=chromadb_status,
        ollama=ollama_status,
    )


def _check_chromadb() -> str:
    if not settings.chroma_db_path.exists():
        return "missing_path"

    try:
        import chromadb
    except ImportError:
        return "package_not_installed"

    try:
        client = chromadb.PersistentClient(path=str(settings.chroma_db_path))
        client.get_collection(name=settings.chroma_collection)
        return "ok"
    except Exception:
        return "unreachable_or_missing_collection"


def _check_ollama() -> str:
    try:
        import ollama
    except ImportError:
        return "package_not_installed"

    try:
        ollama.list()
        return "ok"
    except Exception:
        return "unreachable"