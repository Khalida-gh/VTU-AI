#!/usr/bin/env python3
"""
search_chunks.py

Accepts a user question from the command line, embeds it with the same
BAAI/bge-m3 model used by create_embeddings.py, searches the persistent
ChromaDB collection, and prints the top-k most relevant chunks along
with their similarity scores and metadata.

Usage:
    python search_chunks.py "What is the warranty period for the product?"
    python search_chunks.py --top-k 10 "How do I reset my password?"
    python search_chunks.py --db chroma_db --collection documents "your question"
    python search_chunks.py --verbose "your question"

Requirements:
    pip install sentence-transformers chromadb
"""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path

DEFAULT_MODEL_NAME = "BAAI/bge-m3"


def setup_logging(verbose: bool) -> logging.Logger:
    """Configure console-only logging (this is an interactive query tool)."""
    logger = logging.getLogger("search_chunks")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(fmt="%(levelname)-7s | %(message)s")
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger


def format_result(rank: int, doc: str, metadata: dict, distance: float, wrap_width: int) -> str:
    """Format a single search result for display."""
    # ChromaDB's cosine "distance" is 1 - cosine_similarity for normalized
    # embeddings, so similarity = 1 - distance. Clamp for display safety.
    similarity = 1 - distance
    similarity = max(0.0, min(1.0, similarity))

    chunk_id = metadata.get("chunk_id", "unknown")
    source_file = metadata.get("source_file", "unknown")
    chunk_index = metadata.get("chunk_index", "unknown")
    char_count = metadata.get("char_count", "unknown")

    wrapped_text = textwrap.fill(doc.strip(), width=wrap_width)

    lines = [
        f"[{rank}] similarity: {similarity:.4f}  (distance: {distance:.4f})",
        f"    chunk_id:     {chunk_id}",
        f"    source_file:  {source_file}",
        f"    chunk_index:  {chunk_index}",
        f"    char_count:   {char_count}",
        "    text:",
        textwrap.indent(wrapped_text, "        "),
    ]
    return "\n".join(lines)


def run_search(
    question: str,
    db_dir: Path,
    collection_name: str,
    model_name: str,
    top_k: int,
    logger: logging.Logger,
) -> int:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error(
            "sentence-transformers is not installed. Install it with:\n"
            "    pip install sentence-transformers"
        )
        return 1

    try:
        import chromadb
    except ImportError:
        logger.error(
            "chromadb is not installed. Install it with:\n"
            "    pip install chromadb"
        )
        return 1

    if not db_dir.exists():
        logger.error("ChromaDB directory does not exist: %s", db_dir)
        return 1

    logger.info("Connecting to ChromaDB at %s", db_dir)
    try:
        client = chromadb.PersistentClient(path=str(db_dir))
    except Exception as exc:
        logger.error("FAILED to connect to ChromaDB at %s: %s", db_dir, exc)
        return 1

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as exc:
        logger.error(
            "FAILED to open collection '%s': %s\n"
            "Make sure create_embeddings.py has been run and the collection name matches.",
            collection_name,
            exc,
        )
        return 1

    try:
        count = collection.count()
    except Exception:
        count = None

    if count == 0:
        logger.error("Collection '%s' is empty — nothing to search.", collection_name)
        return 1

    logger.info("Loading embedding model %s...", model_name)
    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:
        logger.error("FAILED to load model %s: %s", model_name, exc)
        return 1

    logger.info("Embedding query and searching top %d result(s)...", top_k)
    try:
        query_embedding = model.encode(
            [question],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        effective_k = top_k if count is None else min(top_k, count)

        results = collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=effective_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("FAILED to query the collection: %s", exc)
        return 1

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        print("No results found.")
        return 0

    print(f"\nTop {len(documents)} result(s) for: \"{question}\"\n")
    print("=" * 70)

    for rank, (doc, metadata, distance) in enumerate(
        zip(documents, metadatas, distances), start=1
    ):
        print(format_result(rank, doc, metadata or {}, distance, wrap_width=88))
        print("-" * 70)

    return 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search a ChromaDB chunk collection using a natural-language "
        "question, embedded with the same model used during indexing."
    )
    parser.add_argument(
        "question",
        type=str,
        help="The question or search query to run",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("chroma_db"),
        help="Directory of the persistent ChromaDB store (default: chroma_db)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="documents",
        help="Name of the ChromaDB collection to search (default: documents)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL_NAME,
        help=f"sentence-transformers model to use — must match the model used "
        f"during indexing (default: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top results to return (default: 5)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG-level) logging",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logger = setup_logging(args.verbose)

    if args.top_k <= 0:
        logger.error("--top-k must be a positive integer (got %d)", args.top_k)
        return 1

    if not args.question or not args.question.strip():
        logger.error("Question cannot be empty")
        return 1

    return run_search(
        question=args.question.strip(),
        db_dir=args.db.resolve(),
        collection_name=args.collection,
        model_name=args.model,
        top_k=args.top_k,
        logger=logger,
    )


if __name__ == "__main__":
    sys.exit(main())