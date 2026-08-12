#!/usr/bin/env python3
"""
chunk_text.py

Recursively scans a source directory (typically the output of
clean_text.py) for .txt files, splits each document into overlapping
chunks of approximately --chunk-size characters (preserving paragraph
boundaries wherever possible), attaches metadata to each chunk, and
writes the result as a JSON file per source document into an output
directory, preserving the original folder structure.

Chunking strategy:
    1. The document is split into paragraphs (blank-line separated).
    2. Paragraphs are packed greedily into chunks up to --chunk-size
       characters, keeping paragraphs intact whenever they fit.
    3. When a paragraph would overflow the current chunk, the chunk is
       finalized and a new one starts with the trailing --overlap
       characters of the previous chunk (trimmed to a clean word
       boundary) carried over for context continuity.
    4. Any single paragraph longer than --chunk-size is itself split by
       sentence boundaries, falling back to word boundaries, falling
       back to a hard character split — so no chunk ever silently
       exceeds the configured size because of one long paragraph.

Output format (one JSON file per source .txt file):
    {
        "source_file": "relative/path/to/file.txt",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "total_chunks": 3,
        "chunks": [
            {
                "chunk_id": "file_0000",
                "chunk_index": 0,
                "char_count": 987,
                "text": "..."
            },
            ...
        ]
    }

Usage:
    python chunk_text.py
    python chunk_text.py --source cleaned_text --output chunks
    python chunk_text.py --chunk-size 1200 --overlap 150
    python chunk_text.py --overwrite --verbose

Requirements:
    Standard library only.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

LOG_FILE_NAME = "chunk_text.log"

PARAGRAPH_SEPARATOR = "\n\n"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
WHITESPACE_RE = re.compile(r"\s")


def setup_logging(output_dir: Path, verbose: bool) -> logging.Logger:
    """Configure logging to both console and a log file inside output_dir."""
    logger = logging.getLogger("chunk_text")
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

    output_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(output_dir / LOG_FILE_NAME, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


# --------------------------------------------------------------------------
# Splitting helpers
# --------------------------------------------------------------------------

def get_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs on blank lines."""
    raw_paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw_paragraphs if p.strip()]


def split_by_words(text: str, chunk_size: int) -> list[str]:
    """
    Fallback splitter for a chunk of text with no usable sentence breaks.
    Packs words up to chunk_size; if a single word itself exceeds
    chunk_size (e.g. a long URL), hard-splits it by character count.
    """
    words = text.split()
    pieces: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip() if current else word

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            pieces.append(current)
            current = ""

        if len(word) > chunk_size:
            for i in range(0, len(word), chunk_size):
                pieces.append(word[i:i + chunk_size])
        else:
            current = word

    if current:
        pieces.append(current)

    return pieces


def split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    """
    Split a single paragraph that exceeds chunk_size into smaller pieces,
    preferring sentence boundaries and falling back to word boundaries
    (and ultimately a hard character split) when needed.
    """
    sentences = SENTENCE_SPLIT_RE.split(paragraph)
    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > chunk_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(split_by_words(sentence, chunk_size))
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = sentence

    if current:
        pieces.append(current)

    return pieces


def build_units(text: str, chunk_size: int) -> list[str]:
    """
    Convert document text into a flat list of "units" (paragraphs, or
    sub-paragraph pieces for oversized paragraphs) suitable for greedy
    packing. Every returned unit is guaranteed to be <= chunk_size.
    """
    units: list[str] = []
    for paragraph in get_paragraphs(text):
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
        else:
            units.extend(split_long_paragraph(paragraph, chunk_size))
    return units


def compute_overlap_text(previous_chunk: str, overlap: int) -> str:
    """
    Take the trailing `overlap` characters of the previous chunk and trim
    to the next whitespace boundary so the carried-over text doesn't
    start mid-word.
    """
    if overlap <= 0 or not previous_chunk:
        return ""

    tail = previous_chunk[-overlap:]
    match = WHITESPACE_RE.search(tail)
    if match:
        tail = tail[match.start() + 1:]
    return tail.strip()


def pack_units(units: list[str], chunk_size: int, overlap: int) -> list[str]:
    """
    Greedily pack units (paragraphs / sub-paragraph pieces) into chunks
    of at most chunk_size characters, carrying `overlap` characters of
    context from the end of one chunk into the start of the next.
    """
    chunks: list[str] = []
    current_parts: list[str] = []

    def joined(parts: list[str]) -> str:
        return PARAGRAPH_SEPARATOR.join(parts)

    for unit in units:
        candidate_parts = current_parts + [unit]
        candidate_text = joined(candidate_parts)

        if current_parts and len(candidate_text) > chunk_size:
            finalized = joined(current_parts)
            chunks.append(finalized)

            overlap_text = compute_overlap_text(finalized, overlap)
            current_parts = [overlap_text] if overlap_text else []
            candidate_parts = current_parts + [unit]
            candidate_text = joined(candidate_parts)

        current_parts = candidate_parts

    if current_parts:
        final_text = joined(current_parts)
        if final_text.strip():
            chunks.append(final_text)

    return [c.strip() for c in chunks if c.strip()]


def chunk_document(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Full pipeline: paragraph-aware chunking with overlap for one document."""
    if not text.strip():
        return []
    units = build_units(text, chunk_size)
    if not units:
        return []
    return pack_units(units, chunk_size, overlap)


# --------------------------------------------------------------------------
# File processing
# --------------------------------------------------------------------------

def build_chunk_records(
    chunks: list[str], source_file: str, chunk_size: int, overlap: int
) -> dict:
    """Assemble the JSON-serializable record for one document's chunks."""
    stem = Path(source_file).stem
    chunk_records = []

    for index, chunk_text_value in enumerate(chunks):
        chunk_records.append(
            {
                "chunk_id": f"{stem}_{index:04d}",
                "chunk_index": index,
                "char_count": len(chunk_text_value),
                "text": chunk_text_value,
            }
        )

    return {
        "source_file": source_file,
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "total_chunks": len(chunk_records),
        "chunks": chunk_records,
    }


def process_directory(
    source_dir: Path,
    output_dir: Path,
    logger: logging.Logger,
    chunk_size: int,
    overlap: int,
    overwrite: bool = False,
) -> dict:
    """
    Walk source_dir for .txt files, chunk each one, and write a JSON
    record to output_dir, preserving relative subfolder structure.
    """
    txt_files = sorted(source_dir.rglob("*.txt"))
    stats = {"total": len(txt_files), "succeeded": 0, "skipped": 0, "failed": 0}

    if not txt_files:
        logger.warning("No .txt files found under: %s", source_dir)
        return stats

    logger.info("Found %d .txt file(s) under %s", len(txt_files), source_dir)
    start_time = time.time()

    for index, txt_path in enumerate(txt_files, start=1):
        relative_path = txt_path.relative_to(source_dir)
        json_relative_path = relative_path.with_suffix(".json")
        output_path = output_dir / json_relative_path

        logger.debug("(%d/%d) Processing: %s", index, stats["total"], relative_path)

        if output_path.exists() and not overwrite:
            logger.info(
                "(%d/%d) SKIP (already exists): %s", index, stats["total"], relative_path
            )
            stats["skipped"] += 1
            continue

        try:
            text = txt_path.read_text(encoding="utf-8", errors="replace")
            chunks = chunk_document(text, chunk_size, overlap)

            if not chunks:
                logger.warning(
                    "(%d/%d) No chunks produced (empty file?): %s",
                    index,
                    stats["total"],
                    relative_path,
                )

            record = build_chunk_records(
                chunks, str(relative_path.as_posix()), chunk_size, overlap
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            logger.info(
                "(%d/%d) OK: %s -> %s (%d chunks)",
                index,
                stats["total"],
                relative_path,
                output_path,
                len(chunks),
            )
            stats["succeeded"] += 1

        except Exception as exc:
            logger.error(
                "(%d/%d) FAILED to process %s: %s",
                index,
                stats["total"],
                relative_path,
                exc,
            )
            stats["failed"] += 1
            continue

    elapsed = time.time() - start_time
    logger.info(
        "Finished in %.2fs — total: %d, succeeded: %d, skipped: %d, failed: %d",
        elapsed,
        stats["total"],
        stats["succeeded"],
        stats["skipped"],
        stats["failed"],
    )
    return stats


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chunk cleaned text files into overlapping, paragraph-aware "
        "chunks and save each document's chunks as JSON."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("cleaned_text"),
        help="Root folder containing .txt files to chunk (default: cleaned_text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("chunks"),
        help="Root folder to write chunk JSON files to (default: chunks)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Approximate maximum characters per chunk (default: 1000)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=200,
        help="Number of overlapping characters carried between chunks (default: 200)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing chunk JSON files instead of skipping them",
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
    output_dir = args.output.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(output_dir, args.verbose)

    if args.chunk_size <= 0:
        logger.error("--chunk-size must be a positive integer (got %d)", args.chunk_size)
        return 1

    if args.overlap < 0:
        logger.error("--overlap cannot be negative (got %d)", args.overlap)
        return 1

    if args.overlap >= args.chunk_size:
        logger.error(
            "--overlap (%d) must be smaller than --chunk-size (%d)",
            args.overlap,
            args.chunk_size,
        )
        return 1

    if not source_dir.exists():
        logger.error("Source directory does not exist: %s", source_dir)
        return 1

    if not source_dir.is_dir():
        logger.error("Source path is not a directory: %s", source_dir)
        return 1

    logger.info("Source directory: %s", source_dir)
    logger.info("Output directory: %s", output_dir)
    logger.info("Chunk size: %d, overlap: %d", args.chunk_size, args.overlap)

    stats = process_directory(
        source_dir=source_dir,
        output_dir=output_dir,
        logger=logger,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        overwrite=args.overwrite,
    )

    if stats["total"] > 0 and stats["succeeded"] == 0 and stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())