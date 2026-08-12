"""POST /generate-answer — retrieves BCS501 context and generates a VTU exam answer.

This endpoint is a thin wrapper: all retrieval and generation logic
lives in the existing scripts/answer_engine.py and is invoked via
backend.engine_bridge.run_pipeline(). Nothing here re-implements ChromaDB
querying or Ollama prompting. As of the single-call refactor, top_k is
no longer a fixed setting passed in from config — it's chosen
dynamically from `marks` inside answer_engine.marks_to_top_k(), so it is
intentionally NOT passed here (leaving it None tells run_pipeline to
compute it).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from . import engine_bridge
from .config import settings
from .schemas import (
    GenerateAnswerRequest,
    GenerateAnswerResponse,
    SourceMetadata,
    TranslateRequest,
    TranslateResponse,
)

logger = logging.getLogger("vtu_api.answer")
router = APIRouter(tags=["answer"])

# Maps engine pipeline failure stages to HTTP status codes. All current
# stages are upstream-dependency issues (ChromaDB/Ollama unreachable,
# empty collection, missing model, etc.), so they map to 503.
_STEP_STATUS_CODES = {
    "retrieval": 503,
    "generation": 503,
}


@router.post("/generate-answer", response_model=GenerateAnswerResponse)
def generate_answer(request: GenerateAnswerRequest) -> GenerateAnswerResponse:
    """
    Accepts a topic, marks, and (optionally) subject, runs the existing
    retrieval -> generate pipeline (single Ollama call), and returns the
    answer plus retrieved source metadata.

    NOTE on `subject`: chunk metadata currently stored by
    create_embeddings.py does not yet include a subject field, so this
    endpoint does not filter retrieval by subject — it simply defaults to
    and echoes back "BCS501" as requested. Once subject metadata is added
    to the indexing pipeline, filtering can be added here without
    touching the existing answer_engine logic.
    """
    print("=" * 60)
    print("POST /generate-answer")
    print("Topic:", request.topic)
    print("Marks:", request.marks)
    print("Subject:", request.subject)
    print("=" * 60)

    try:
        result = engine_bridge.run_pipeline(
            topic=request.topic,
            marks=request.marks,
            db_path=settings.chroma_db_path,
            collection=settings.chroma_collection,
            embed_model=settings.embed_model,
            llm_model=settings.ollama_model,
            # top_k intentionally omitted (defaults to None): run_pipeline
            # derives it from `marks` via answer_engine.marks_to_top_k().
        )
        print("PIPELINE RETURNED")
        print(type(result))
        print(result.keys())
    except engine_bridge.EngineError as exc:
        logger.error("Answer engine failed at step '%s': %s", exc.step, exc.message)
        status_code = _STEP_STATUS_CODES.get(exc.step, 500)
        raise HTTPException(
            status_code=status_code,
            detail={"step": exc.step, "message": exc.message},
        ) from exc
    except Exception as exc:  # unexpected/unhandled failure
        logger.exception("Unexpected error while generating answer")
        raise HTTPException(
            status_code=500, detail=f"Unexpected server error: {exc}"
        ) from exc
    print("BUILDING SOURCES")
    sources = [
        SourceMetadata(
            chunk_id=chunk["chunk_id"],
            source_file=chunk["source_file"],
            chunk_index=chunk["chunk_index"],
            char_count=chunk["char_count"],
            similarity=chunk["similarity"],
        )
        for chunk in result["sources"]
    ]
    print("RETURNING RESPONSE")
    return GenerateAnswerResponse(
        answer=result["answer"],
        topic=request.topic,
        marks=request.marks,
        subject=request.subject,
        sources=sources,
        plan=result.get("plan"),
    )
@router.post("/translate", response_model=TranslateResponse)
def translate_answer(request: TranslateRequest) -> TranslateResponse:
    """
    Translate an existing VTU answer into the requested language.

    Uses the existing Ollama model so no external translation API is required.
    """

    pprompt = f"""
You are a professional multilingual translator for an Indian university
exam-answer system.

TARGET LANGUAGE: {request.language}

You MUST translate the answer into the EXACT target language requested.

LANGUAGE REQUIREMENTS:
- Hindi = Hindi written in Devanagari script (हिन्दी)
- Kannada = Kannada written in Kannada script (ಕನ್ನಡ)
- Telugu = Telugu written in Telugu script (తెలుగు)
- Tamil = Tamil written in Tamil script (தமிழ்)
- Marathi = Marathi written in Devanagari script (मराठी)
- English = English written in Latin script

CRITICAL:
- If the target language is Kannada, output ONLY Kannada.
- NEVER output Sinhala when Kannada is requested.
- If the target language is Hindi or Marathi, use Devanagari, NOT Sinhala.
- If the target language is Telugu, use Telugu script.
- If the target language is Tamil, use Tamil script.
- Do not substitute another language that merely looks similar.
- Do not transliterate the target language into English letters.

TRANSLATION RULES:
1. Preserve the original meaning exactly.
2. Do not add new information.
3. Do not remove important information.
4. Preserve Markdown formatting.
5. Preserve headings, bullet points, numbered lists, bold text,
   formulas, symbols, and code where possible.
6. Translate only natural-language text.
7. Keep technical terms accurate and understandable for a VTU student.
8. Return ONLY the translated answer.
9. Do not add explanations such as "Here is the translation".
10. Do not mention the target language or translation process.

ANSWER TO TRANSLATE:

{request.answer}
"""

    try:
        result = engine_bridge.run_translation(
            prompt=pprompt,
            llm_model=settings.ollama_model,
        )

        return TranslateResponse( 
            translated_answer=result,
            language=request.language,
        )

    except Exception as exc:
        logger.exception("Translation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {exc}",
        ) from exc