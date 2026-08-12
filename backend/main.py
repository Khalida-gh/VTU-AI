"""
FastAPI backend for the VTU AI project.

Run with:
    uvicorn backend.main:app --reload

This app is a thin HTTP layer over the existing ChromaDB retrieval and
Qwen2.5:7b answer-generation logic in scripts/answer_engine.py — see
backend/engine_bridge.py for how that logic is reused (not duplicated).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from . import answer, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)

app = FastAPI(
    title="VTU AI Answer Engine API",
    description=(
        "FastAPI backend wrapping the existing ChromaDB retrieval + "
        "Qwen2.5:7b answer engine for BCS501 (extensible to future subjects)."
    ),
    version="1.0.0",
)

# CORS: wide open by default for local frontend development. Set the
# CORS_ORIGINS environment variable (comma-separated) to restrict this
# before deploying anywhere public, e.g.:
#     CORS_ORIGINS=https://your-frontend.example.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(answer.router)