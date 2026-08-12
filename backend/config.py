"""
Centralized configuration for the FastAPI backend.

All settings can be overridden with environment variables so the same
codebase works across dev/staging/prod without code changes:

    CHROMA_DB_PATH     - path to the persistent ChromaDB store (default: chroma_db)
    CHROMA_COLLECTION  - ChromaDB collection name (default: documents)
    EMBED_MODEL        - sentence-transformers embedding model (default: BAAI/bge-m3)
    OLLAMA_MODEL       - Ollama model for answer generation (default: qwen2.5:7b)
    TOP_K              - number of chunks to retrieve per query (default: 5)
    DEFAULT_SUBJECT    - default subject code when the client omits it (default: BCS501)
    CORS_ORIGINS       - comma-separated list of allowed origins (default: * for now)
"""

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.chroma_db_path: Path = Path(
            os.environ.get("CHROMA_DB_PATH", "chroma_db")
        ).resolve()
        self.chroma_collection: str = os.environ.get("CHROMA_COLLECTION", "documents")
        self.embed_model: str = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")
        self.ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        self.top_k: int = int(os.environ.get("TOP_K", "5"))
        self.default_subject: str = os.environ.get("DEFAULT_SUBJECT", "BCS501")

        cors_env = os.environ.get("CORS_ORIGINS", "*")
        self.cors_origins: list[str] = [o.strip() for o in cors_env.split(",") if o.strip()]


settings = Settings()