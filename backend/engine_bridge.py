"""
Thin bridge between the FastAPI backend and the existing, unmodified
scripts/answer_engine.py.

This module deliberately contains NO retrieval logic and NO Ollama
prompt logic of its own — it only imports and calls the functions that
already exist in scripts/answer_engine.py (retrieve_chunks,
marks_to_top_k, build_prompt, call_ollama) and reshapes their results
into plain data structures the API layer can turn into JSON. If you
improve the CLI's retrieval or generation logic later, the API picks up
the change automatically with no duplication to keep in sync.

NOTE: as of the single-call refactor, answer_engine.py no longer has a
separate planning step (it used to make two Ollama calls: plan, then
answer). This bridge now makes exactly one Ollama call per request, and
top_k is chosen automatically from `marks` via answer_engine.marks_to_top_k()
unless the caller passes an explicit override.
"""

from __future__ import annotations
import time
import sys
from pathlib import Path
from typing import Any

# scripts/answer_engine.py lives alongside this project's `scripts/` folder,
# not inside the `backend/` package. Make sure it's importable regardless of
# the working directory the API is launched from (e.g. `uvicorn backend.main:app`).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import answer_engine  # the existing, unmodified CLI module
except ImportError as exc:  # pragma: no cover - fails fast at startup, not per-request
    raise ImportError(
        f"Could not import the existing answer_engine module from '{_SCRIPTS_DIR}'. "
        "Make sure scripts/answer_engine.py exists relative to the project root, "
        "or adjust _SCRIPTS_DIR in backend/engine_bridge.py to match your layout."
    ) from exc


class EngineError(Exception):
    """
    Raised when a step of the existing answer_engine pipeline reports an
    error (retrieval or generation). Carries the step name so the API
    layer can map it to an appropriate HTTP status code.
    """

    def __init__(self, step: str, message: str):
        self.step = step
        self.message = message
        super().__init__(f"[{step}] {message}")


def run_pipeline(
    topic: str,
    marks: int,
    db_path: Path,
    collection: str,
    embed_model: str,
    llm_model: str,
    top_k: int | None = None,
) -> dict[str, Any]:
    """
    Run the existing answer_engine pipeline end to end and return a
    structured result instead of printing to stdout.

    Mirrors answer_engine.main()'s call sequence exactly:
        retrieve_chunks -> build_prompt -> call_ollama (single call)

    If top_k is None (the default), it is chosen automatically from
    `marks` via answer_engine.marks_to_top_k() — the same dynamic sizing
    the CLI uses. Pass an explicit top_k to override that.

    Raises EngineError with a `step` of "retrieval" or "generation" if
    either stage fails, so callers can respond appropriately.
    """
    effective_top_k = top_k if top_k is not None else answer_engine.marks_to_top_k(marks)
    start = time.perf_counter()
    chunks, error = answer_engine.retrieve_chunks(
        topic=topic,
        db_path=db_path,
        collection_name=collection,
        embed_model_name=embed_model,
        top_k=effective_top_k,
    )
    print(f"Retrieval time: {time.perf_counter() - start:.2f} sec")

    prompt_start = time.perf_counter()
    if error:
        raise EngineError("retrieval", error)

    if not chunks:
        raise EngineError(
            "retrieval", "No relevant chunks were retrieved for this topic."
        )

    prompt = answer_engine.build_prompt(topic, marks, chunks)
    print(f"Prompt build time: {time.perf_counter() - prompt_start:.2f} sec")

    llm_start = time.perf_counter()

    answer, error = answer_engine.call_ollama(prompt, llm_model)
    print(f"Ollama time: {time.perf_counter() - llm_start:.2f} sec")
    print(f"Total pipeline: {time.perf_counter() - start:.2f} sec")
    if error:
        raise EngineError("generation", error)

    return {
        "answer": answer,
        "sources": chunks,  # list of dicts: chunk_id, source_file, chunk_index, char_count, text, similarity
    }
def run_translation(
    prompt: str,
    llm_model: str,
) -> str:
    """
    Send a translation prompt to the existing Ollama/Qwen model.

    This reuses the same call_ollama() function as the normal
    answer-generation pipeline.
    """

    start = time.perf_counter()

    translated, error = answer_engine.call_ollama(
        prompt,
        llm_model,
    )

    print(
        f"Translation Ollama time: "
        f"{time.perf_counter() - start:.2f} sec"
    )

    if error:
        raise EngineError("generation", error)

    return translated