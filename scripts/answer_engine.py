#!/usr/bin/env python3
"""
answer_engine.py

A retrieval-augmented answer generator for BCS501 exam-style questions.

Pipeline (single Ollama call — no separate planning step):
    1. Embed the topic with the same BAAI/bge-m3 model used to build the
       ChromaDB index (create_embeddings.py).
    2. Retrieve the top-k most relevant chunks from the existing
       ChromaDB collection. top_k is chosen automatically based on the
       requested marks (higher marks -> more context retrieved), unless
       overridden with --top-k.
    3. Send ONE prompt to the local Ollama model (qwen2.5:7b by default)
       that both grounds the answer strictly in the retrieved context and
       instructs the model on structure/depth for the requested marks, in
       Markdown (headings, numbered/bulleted points, **bold** VTU
       keywords) — all in a single generation call for speed.
    4. Print the retrieved sources/chunk IDs first (for debugging /
       citation tracing), then the final Markdown answer.

The model is never given outside knowledge or a web-search tool — the
prompt is strictly grounded in the chunks retrieved from ChromaDB for
this run.

Usage:
    python answer_engine.py "Software Engineering process models" --marks 10
    python answer_engine.py "agile methodology" --marks 5
    python answer_engine.py "waterfall model" --marks 2 --db chroma_db --collection documents
    python answer_engine.py "risk management" --marks 20 --model qwen2.5:7b --verbose

Requirements:
    pip install sentence-transformers chromadb ollama
"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
DEFAULT_LLM_MODEL = "qwen2.5:7b"

# Embedding model cache. Loaded lazily on first call to retrieve_chunks()
# and reused on every subsequent call so we never pay model-load cost
# more than once per process.
_EMBED_MODEL = None


# --------------------------------------------------------------------------
# Marks-based guidance
# --------------------------------------------------------------------------

def marks_guidance(marks: int) -> str:
    """Return Markdown length/structure guidance appropriate for the given marks."""
    if marks <= 2:
        return (
            "2-mark answer: 2-4 concise sentences giving a direct definition or "
            "explanation. No headings needed — a single short paragraph is fine, "
            "but **bold** the 1-2 most important VTU keywords in it."
        )
    if marks <= 5:
        return (
            "5-mark answer: a short introductory sentence, then 7-8 bulleted "
            "points (`- point`). One `##` heading is optional. **Bold** each "
            "key term the first time it appears. Each point must be a distinct "
            "idea from the context, not a restatement of another point."
        )
    if marks <= 8:
        return (
            "8-mark answer: a brief intro paragraph, then 2-3 `##` sections, "
            "each with 3-5 bulleted or numbered points. **Bold** important "
            "keywords/terms within the points."
        )
    if marks <= 10:
        return (
            "10-mark answer: a brief introduction, then 4-5 `##` sections each "
            "with numbered or bulleted sub-points, and examples or a diagram "
            "description ONLY if such details are present in the context. "
            "**Bold** key terms. A short concluding line is fine if the context "
            "supports one."
        )
    if marks <= 12:
        return (
            "12-mark answer: a brief introduction, then 6-7 `##` sections each "
            "with numbered or bulleted sub-points (use nested bullets for "
            "sub-details where useful). **Bold** key terms and definitions. "
            "Include examples/diagram descriptions/comparisons ONLY where the "
            "context supports them, plus a short conclusion."
        )
    if marks <= 15:
        return (
            "15-mark answer: a comprehensive answer — short introduction, then "
            "5-6 clearly labeled `##` sections (e.g. definition, "
            "characteristics/types, process/steps, advantages/disadvantages, "
            "examples — include only the sections the context actually "
            "supports), each with numbered/bulleted sub-points and nested "
            "bullets for detail. **Bold** all key VTU terminology. Add a "
            "comparison table (Markdown table) ONLY if the context contains "
            "comparable items. End with a brief conclusion."
        )
    return (
        "20-mark answer: the most comprehensive answer — short introduction, "
        "then 6+ clearly labeled `##` sections covering every distinct aspect "
        "present in the context (definition, types/categories, detailed "
        "process/steps, advantages/disadvantages/limitations, examples, "
        "comparisons — include only what the context supports), with numbered "
        "sub-points and nested bullets for depth. **Bold** all key VTU "
        "terminology and definitions. Use a Markdown comparison table ONLY if "
        "the context contains genuinely comparable items. End with a short "
        "conclusion. Do not pad with generic filler — every point must be "
        "traceable to the retrieved context, even at this length."
    )


# Approximate number of chunks to retrieve for each marks tier. Higher marks
# need more supporting context to fill a longer, more detailed answer without
# repeating the same 1-2 chunks. Falls back to nearest-tier for any marks
# value outside this list rather than erroring out.
_MARKS_TOP_K = {
    2: 2,
    5: 3,
    8: 4,
    10: 5,
    12: 6,
    15: 7,
    20: 8,
}


def marks_to_top_k(marks: int) -> int:
    """Dynamically choose how many chunks to retrieve based on the requested marks."""
    if marks in _MARKS_TOP_K:
        return _MARKS_TOP_K[marks]
    # Unlisted marks value: fall back to whichever configured tier is
    # numerically closest, rather than erroring out.
    nearest = min(_MARKS_TOP_K, key=lambda m: abs(m - marks))
    return _MARKS_TOP_K[nearest]


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def format_context(chunks: list[dict]) -> str:
    blocks = [
        f"[Context {i} | chunk_id: {c['chunk_id']}]\n{c['text']}"
        for i, c in enumerate(chunks, start=1)
    ]
    return "\n\n".join(blocks) if blocks else "(no context retrieved)"


def build_prompt(topic: str, marks: int, chunks: list[dict]) -> str:
    """
    Build the single strict, context-only VTU exam-answer prompt.
    Analysis of the context/marks and writing of the final answer both
    happen in this one generation call — there is no separate planning
    request, so this is the only prompt sent to Ollama per question.
    """
    context_text = format_context(chunks)[:6000]
    guidance = marks_guidance(marks)

    return f"""
You are an expert VTU (Visvesvaraya Technological University) exam answer writer.

IMPORTANT LANGUAGE RULES:
- Respond ONLY in English.
- Never generate Chinese, Japanese, Korean, Arabic, Hindi, or any other language.
- If retrieved notes contain another language, translate them into English.
- Never switch languages in the middle of the answer.

STRICT RULES:
1. Use ONLY the CONTEXT below.
2. Never use your own knowledge.
3. If information is missing, clearly write:
   "The retrieved notes contain only partial information for this topic."
4. Write the answer exactly suitable for {marks} marks.
5. Follow this formatting:
   - Start with a short introduction.
   - Use ## headings.
   - Use numbered lists.
   - Use bullet points.
   - **Bold every important VTU keyword.**
   - Keep paragraphs short.
6. Do NOT mention AI, context, retrieval, or these instructions.

QUESTION:
{topic}

MARKS:
{marks}

ANSWER STYLE:
{guidance}

CONTEXT:
{context_text}

Write only the final answer in Markdown.
"""


# --------------------------------------------------------------------------
# Retrieval (unchanged behavior from the working version)
# --------------------------------------------------------------------------

def retrieve_chunks(
    topic: str,
    db_path: Path,
    collection_name: str,
    embed_model_name: str,
    top_k: int,
):
    """
    Embed the topic and query ChromaDB for the top-k most relevant chunks.
    Returns (chunks, error_message). On success error_message is None.
    Each chunk dict has: chunk_id, source_file, chunk_index, char_count,
    text, similarity.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None, (
            "sentence-transformers is not installed. Install it with:\n"
            "    pip install sentence-transformers"
        )

    try:
        import chromadb
    except ImportError:
        return None, (
            "chromadb is not installed. Install it with:\n"
            "    pip install chromadb"
        )

    if not db_path.exists():
        return None, f"ChromaDB directory does not exist: {db_path}"

    try:
        client = chromadb.PersistentClient(path=str(db_path))
    except Exception as exc:
        return None, f"Failed to connect to ChromaDB at {db_path}: {exc}"

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as exc:
        return None, (
            f"Failed to open collection '{collection_name}': {exc}\n"
            "Make sure create_embeddings.py has been run and the collection "
            "name matches."
        )

    try:
        count = collection.count()
    except Exception:
        count = None

    if count == 0:
        return None, f"Collection '{collection_name}' is empty — nothing to retrieve."

    global _EMBED_MODEL

    try:
        if _EMBED_MODEL is None:
            print("Loading embedding model...")
            _EMBED_MODEL = SentenceTransformer(embed_model_name)

        model = _EMBED_MODEL

    except Exception as exc:
        return None, f"Failed to load embedding model '{embed_model_name}': {exc}"

    try:
        query_embedding = model.encode(
            [topic], normalize_embeddings=True, convert_to_numpy=True
        )
        effective_k = top_k if count is None else min(top_k, count)

        results = collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=effective_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        return None, f"Failed to query the collection: {exc}"

    try:
        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        chunks = []
        for i, text in enumerate(documents):
            distance = distances[i] if i < len(distances) else 1.0
            similarity = max(0.0, min(1.0, 1 - distance))
            meta = metadatas[i] if i < len(metadatas) else {}
            meta = meta or {}

            chunk_id = ids[i] if i < len(ids) else meta.get("chunk_id", str(i))

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", i),
                    "char_count": len(text),
                    "text": text,
                    "similarity": similarity,
                }
            )
    except Exception as exc:
        return None, f"Failed to parse retrieval results: {exc}"

    return chunks, None


# --------------------------------------------------------------------------
# Generation (Ollama / Qwen2.5:7b) — single call
# --------------------------------------------------------------------------

def call_ollama(prompt: str, llm_model_name: str):
    import ollama

    print("=" * 80)
    print("PROMPT LENGTH:", len(prompt))
    print("=" * 80)
    print(prompt[:1000])  # print first 1000 chars
    print("=" * 80)

    response = ollama.chat(
    model=llm_model_name,
    options={
        "temperature": 0.1,
        "top_p": 0.9,
    },
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
)

    return response["message"]["content"], None

# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------

def print_sources(chunks: list[dict]) -> None:
    print("=" * 70)
    print(f"RETRIEVED SOURCES ({len(chunks)} chunk(s))")
    print("=" * 70)
    for i, chunk in enumerate(chunks, start=1):
        print(
            f"[{i}] chunk_id={chunk['chunk_id']}  "
            f"source_file={chunk['source_file']}  "
            f"chunk_index={chunk['chunk_index']}  "
            f"similarity={chunk['similarity']:.4f}"
        )
    print()


def print_answer(answer: str, topic: str, marks: int) -> None:
    print("=" * 70)
    print(f"ANSWER — {topic} ({marks} marks)")
    print("=" * 70)
    print(answer)
    print()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve relevant BCS501 chunks from ChromaDB and generate "
        "a strict, context-only VTU exam answer using a single call to a "
        "local Ollama model."
    )
    parser.add_argument(
        "topic",
        type=str,
        help="The topic/keyword or question to answer",
    )
    parser.add_argument(
        "--marks",
        type=int,
        required=True,
        help="Marks the answer should be suitable for (supported: 2, 5, 8, 10, 12, 15, 20)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="chroma_db",
        help="Directory of the persistent ChromaDB store (default: chroma_db)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="documents",
        help="Name of the ChromaDB collection to search (default: documents)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Number of top chunks to retrieve. If omitted, this is chosen "
        "automatically based on --marks (see marks_to_top_k).",
    )
    parser.add_argument(
        "--embed-model",
        type=str,
        default=DEFAULT_EMBED_MODEL,
        help=f"sentence-transformers embedding model — must match the model used "
        f"during indexing (default: {DEFAULT_EMBED_MODEL})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_LLM_MODEL,
        help=f"Ollama model to use for answer generation (default: {DEFAULT_LLM_MODEL})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the full prompt sent to the model, for debugging",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    topic = args.topic.strip()
    if not topic:
        print("Error: topic cannot be empty.", file=sys.stderr)
        return 1

    if args.marks <= 0:
        print(f"Error: --marks must be a positive integer (got {args.marks}).", file=sys.stderr)
        return 1

    if args.top_k is not None and args.top_k <= 0:
        print(f"Error: --top-k must be a positive integer (got {args.top_k}).", file=sys.stderr)
        return 1

    db_path = Path(args.db).resolve()
    top_k = args.top_k if args.top_k is not None else marks_to_top_k(args.marks)

    # --- Retrieval (unchanged) --------------------------------------------
    chunks, error = retrieve_chunks(
        topic=topic,
        db_path=db_path,
        collection_name=args.collection,
        embed_model_name=args.embed_model,
        top_k=top_k,
    )
    if error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print_sources(chunks)

    if not chunks:
        print("No relevant chunks were retrieved; cannot generate a grounded answer.")
        return 1

    # --- Single generation call --------------------------------------------
    prompt = build_prompt(topic, args.marks, chunks)

    if args.verbose:
        print("-" * 70)
        print("PROMPT SENT TO MODEL:")
        print("-" * 70)
        print(prompt)
        print("-" * 70)
        print()

    answer, error = call_ollama(prompt, args.model)
    if error:
        print(f"Error during answer generation: {error}", file=sys.stderr)
        return 1

    print_answer(answer, topic, args.marks)
    return 0


if __name__ == "__main__":
    sys.exit(main())