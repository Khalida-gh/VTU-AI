#!/usr/bin/env python3
"""
create_embeddings.py

Reads all JSON chunk files produced by chunk_text.py from a source
directory, generates embeddings for every chunk using the BAAI/bge-m3
model via sentence-transformers, and stores each chunk's text,
embedding, and metadata in a persistent ChromaDB collection.

Expected input JSON shape (one file per source document, as produced by
chunk_text.py):
    {
        "source_file": "relative/path/to/file.txt",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "total_chunks": 3,
        "chunks": [
            {"chunk_id": "file_0000", "chunk_index": 0, "char_count": 987, "text": "..."},
            ...
        ]
    }

Each chunk is stored in ChromaDB with:
    - id:        f"{source_file}__{chunk_id}" (sanitized) — globally unique
                 even if two different source files happen to reuse the
                 same chunk_id.
    - document:  the chunk's text
    - embedding: the BAAI/bge-m3 vector for that text
    - metadata:  {"chunk_id", "source_file", "chunk_index", "char_count"}

Duplicate handling:
    Before inserting a batch, existing IDs already present in the
    collection are looked up and skipped — so re-running this script
    over the same chunks folder will not create duplicate entries.
    Use --overwrite-existing to force re-embedding and replace them.

Usage:
    python create_embeddings.py
    python create_embeddings.py --source chunks --db chroma_db --collection documents
    python create_embeddings.py --batch-size 64 --verbose
    python create_embeddings.py --overwrite-existing

Requirements:
    pip install sentence-transformers chromadb
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

LOG_FILE_NAME = "create_embeddings.log"
DEFAULT_MODEL_NAME = "BAAI/bge-m3"

# Characters that are safe inside a Chroma document ID
ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def setup_logging(log_dir: Path, verbose: bool) -> logging.Logger:
    """Configure logging to both console and a log file inside log_dir."""
    logger = logging.getLogger("create_embeddings")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / LOG_FILE_NAME, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def sanitize_id_component(value: str) -> str:
    """Make a string safe to use as (part of) a Chroma document ID."""
    return ID_SANITIZE_RE.sub("_", value).strip("_")


def load_chunk_records(source_dir: Path, logger: logging.Logger) -> list[dict]:
    """
    Recursively load every *.json file under source_dir (as produced by
    chunk_text.py) and flatten them into a list of chunk records, each
    with a globally unique 'id' plus 'text' and metadata fields.

    Malformed or unreadable JSON files are logged and skipped rather
    than aborting the whole run.
    """
    json_files = sorted(source_dir.rglob("*.json"))
    if not json_files:
        logger.warning("No JSON chunk files found under: %s", source_dir)
        return []

    logger.info("Found %d JSON chunk file(s) under %s", len(json_files), source_dir)

    records: list[dict] = []

    for json_path in json_files:
        relative_path = json_path.relative_to(source_dir)
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("FAILED to read/parse %s: %s", relative_path, exc)
            continue

        source_file = data.get("source_file", str(relative_path))
        chunks = data.get("chunks", [])

        if not chunks:
            logger.warning("No chunks found in %s — skipping", relative_path)
            continue

        for chunk in chunks:
            try:
                chunk_id = str(chunk["chunk_id"])
                text = chunk["text"]
                chunk_index = chunk.get("chunk_index")
                char_count = chunk.get("char_count", len(text))
            except KeyError as exc:
                logger.error(
                    "Skipping malformed chunk in %s (missing field %s)",
                    relative_path,
                    exc,
                )
                continue

            if not text or not text.strip():
                logger.warning(
                    "Skipping empty-text chunk %s in %s", chunk_id, relative_path
                )
                continue

            unique_id = (
                f"{sanitize_id_component(source_file)}__{sanitize_id_component(chunk_id)}"
            )

            records.append(
                {
                    "id": unique_id,
                    "text": text,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "source_file": source_file,
                        "chunk_index": chunk_index,
                        "char_count": char_count,
                    },
                }
            )

    logger.info("Loaded %d chunk record(s) total", len(records))
    return records


def batched(items: list, batch_size: int):
    """Yield successive batch_size-sized slices of items."""
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def process_records(
    records: list[dict],
    collection,
    model,
    batch_size: int,
    logger: logging.Logger,
    overwrite_existing: bool,
) -> dict:
    """
    Embed and store records in the ChromaDB collection in batches,
    skipping IDs that already exist unless overwrite_existing is set.
    """
    stats = {"total": len(records), "added": 0, "skipped_duplicate": 0, "failed": 0}

    if not records:
        return stats

    total_batches = (len(records) + batch_size - 1) // batch_size
    start_time = time.time()

    for batch_num, batch in enumerate(batched(records, batch_size), start=1):
        batch_ids = [r["id"] for r in batch]

        try:
            existing = collection.get(ids=batch_ids)
            existing_ids = set(existing.get("ids", []))
        except Exception as exc:
            logger.error(
                "Batch %d/%d: failed to check existing IDs (%s) — assuming none exist",
                batch_num,
                total_batches,
                exc,
            )
            existing_ids = set()

        if overwrite_existing and existing_ids:
            try:
                collection.delete(ids=list(existing_ids))
                logger.debug(
                    "Batch %d/%d: deleted %d existing record(s) for re-embedding",
                    batch_num,
                    total_batches,
                    len(existing_ids),
                )
                existing_ids = set()
            except Exception as exc:
                logger.error(
                    "Batch %d/%d: failed to delete existing records for overwrite: %s",
                    batch_num,
                    total_batches,
                    exc,
                )

        to_insert = [r for r in batch if r["id"] not in existing_ids]
        skipped = len(batch) - len(to_insert)
        stats["skipped_duplicate"] += skipped

        if skipped:
            logger.info(
                "Batch %d/%d: skipping %d already-embedded chunk(s)",
                batch_num,
                total_batches,
                skipped,
            )

        if not to_insert:
            logger.debug(
                "Batch %d/%d: nothing new to embed", batch_num, total_batches
            )
            continue

        try:
            texts = [r["text"] for r in to_insert]
            ids = [r["id"] for r in to_insert]
            metadatas = [r["metadata"] for r in to_insert]

            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

            collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=texts,
                metadatas=metadatas,
            )

            stats["added"] += len(to_insert)
            logger.info(
                "Batch %d/%d: embedded and stored %d chunk(s) (%d/%d total so far)",
                batch_num,
                total_batches,
                len(to_insert),
                stats["added"],
                stats["total"] - stats["skipped_duplicate"],
            )

        except Exception as exc:
            logger.error(
                "Batch %d/%d: FAILED to embed/store %d chunk(s): %s",
                batch_num,
                total_batches,
                len(to_insert),
                exc,
            )
            stats["failed"] += len(to_insert)
            continue

    elapsed = time.time() - start_time
    logger.info(
        "Finished in %.2fs — total: %d, added: %d, skipped (duplicate): %d, failed: %d",
        elapsed,
        stats["total"],
        stats["added"],
        stats["skipped_duplicate"],
        stats["failed"],
    )
    return stats


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate BAAI/bge-m3 embeddings for chunked text and store "
        "them in a persistent ChromaDB collection."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("chunks"),
        help="Root folder containing chunk JSON files (default: chunks)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("chroma_db"),
        help="Directory for the persistent ChromaDB store (default: chroma_db)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="documents",
        help="Name of the ChromaDB collection to use (default: documents)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Number of chunks to embed/insert per batch (default: 32)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL_NAME,
        help=f"sentence-transformers model to use (default: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Re-embed and replace chunks whose IDs already exist in the collection "
        "(default: skip duplicates)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG-level) console logging",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    source_dir = args.source.resolve()
    db_dir = args.db.resolve()

    if args.batch_size <= 0:
        print(f"--batch-size must be a positive integer (got {args.batch_size})", file=sys.stderr)
        return 1

    db_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(db_dir, args.verbose)

    if not source_dir.exists():
        logger.error("Source directory does not exist: %s", source_dir)
        return 1

    if not source_dir.is_dir():
        logger.error("Source path is not a directory: %s", source_dir)
        return 1

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

    logger.info("Source directory: %s", source_dir)
    logger.info("ChromaDB path: %s", db_dir)
    logger.info("Collection: %s", args.collection)
    logger.info("Model: %s", args.model)
    logger.info("Batch size: %d", args.batch_size)

    logger.info("Loading model %s (this may take a while on first run)...", args.model)
    try:
        model = SentenceTransformer(args.model)
    except Exception as exc:
        logger.error("FAILED to load model %s: %s", args.model, exc)
        return 1
    logger.info("Model loaded successfully")

    try:
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_or_create_collection(
            name=args.collection,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        logger.error("FAILED to initialize ChromaDB collection: %s", exc)
        return 1

    records = load_chunk_records(source_dir, logger)
    if not records:
        logger.warning("No chunk records to embed. Exiting.")
        return 0

    stats = process_records(
        records=records,
        collection=collection,
        model=model,
        batch_size=args.batch_size,
        logger=logger,
        overwrite_existing=args.overwrite_existing,
    )

    try:
        logger.info("Collection '%s' now contains %d record(s)", args.collection, collection.count())
    except Exception as exc:
        logger.warning("Could not fetch final collection count: %s", exc)

    if stats["total"] > 0 and stats["added"] == 0 and stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())