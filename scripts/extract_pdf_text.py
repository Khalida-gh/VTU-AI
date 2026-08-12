#!/usr/bin/env python3
"""
extract_pdf_text.py

Recursively scans a source directory for PDF files, extracts their text
using PyMuPDF (fitz), and writes each one out as a .txt file in a mirrored
folder structure under an output directory.

Features:
    - Recursive scan of nested subfolders
    - Preserves relative folder structure in the output directory
    - Structured logging to console and a log file
    - Gracefully skips corrupted / unreadable / encrypted PDFs
    - Command-line interface with --source and --output
    - Summary report at the end of the run

Usage:
    python extract_pdf_text.py
    python extract_pdf_text.py --source data/BCS501 --output extracted_text
    python extract_pdf_text.py --source data/BCS501 --output extracted_text --overwrite
    python extract_pdf_text.py --verbose

Requirements:
    pip install pymupdf
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit(
        "PyMuPDF is not installed. Install it with:\n"
        "    pip install pymupdf"
    )


LOG_FILE_NAME = "extract_pdf_text.log"


def setup_logging(output_dir: Path, verbose: bool) -> logging.Logger:
    """Configure logging to both console and a log file inside output_dir."""
    logger = logging.getLogger("extract_pdf_text")
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


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract and return all text from a PDF file, page by page.

    Raises whatever exception PyMuPDF raises on failure (e.g. corrupted
    file, unsupported format, encrypted document); the caller is
    responsible for catching and logging it.
    """
    text_parts = []
    with fitz.open(pdf_path) as doc:
        if doc.is_encrypted:
            # Try an empty-password unlock (common for "owner-password only"
            # PDFs); if that fails, raise so the caller can skip it.
            if not doc.authenticate(""):
                raise ValueError("PDF is encrypted and could not be unlocked")

        if doc.page_count == 0:
            raise ValueError("PDF has no pages")

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            text_parts.append(f"--- Page {page_num} ---\n{page_text}")

    return "\n\n".join(text_parts)


def process_directory(
    source_dir: Path,
    output_dir: Path,
    logger: logging.Logger,
    overwrite: bool = False,
) -> dict:
    """
    Walk source_dir for PDFs and write extracted text to output_dir,
    preserving relative subfolder structure.

    Returns a summary dict with counts of succeeded / skipped / failed files.
    """
    pdf_files = sorted(source_dir.rglob("*.pdf"))
    stats = {"total": len(pdf_files), "succeeded": 0, "skipped": 0, "failed": 0}

    if not pdf_files:
        logger.warning("No PDF files found under: %s", source_dir)
        return stats

    logger.info("Found %d PDF file(s) under %s", len(pdf_files), source_dir)

    start_time = time.time()

    for index, pdf_path in enumerate(pdf_files, start=1):
        relative_path = pdf_path.relative_to(source_dir)
        txt_relative_path = relative_path.with_suffix(".txt")
        txt_output_path = output_dir / txt_relative_path

        logger.debug("(%d/%d) Processing: %s", index, stats["total"], relative_path)

        if txt_output_path.exists() and not overwrite:
            logger.info(
                "(%d/%d) SKIP (already exists): %s", index, stats["total"], relative_path
            )
            stats["skipped"] += 1
            continue

        try:
            txt_output_path.parent.mkdir(parents=True, exist_ok=True)
            text = extract_text_from_pdf(pdf_path)

            if not text.strip():
                logger.warning(
                    "(%d/%d) No extractable text (possibly scanned/image-only): %s",
                    index,
                    stats["total"],
                    relative_path,
                )

            txt_output_path.write_text(text, encoding="utf-8")
            logger.info(
                "(%d/%d) OK: %s -> %s", index, stats["total"], relative_path, txt_output_path
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


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursively extract text from PDFs using PyMuPDF, "
        "preserving folder structure in the output directory."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/BCS501"),
        help="Root folder to scan for PDFs (default: data/BCS501)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("extracted_text"),
        help="Root folder to write extracted .txt files to (default: extracted_text)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .txt files instead of skipping them",
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

    if not source_dir.exists():
        logger.error("Source directory does not exist: %s", source_dir)
        return 1

    if not source_dir.is_dir():
        logger.error("Source path is not a directory: %s", source_dir)
        return 1

    logger.info("Source directory: %s", source_dir)
    logger.info("Output directory: %s", output_dir)

    stats = process_directory(
        source_dir=source_dir,
        output_dir=output_dir,
        logger=logger,
        overwrite=args.overwrite,
    )

    # Non-zero exit code if every single PDF failed (but some were found)
    if stats["total"] > 0 and stats["succeeded"] == 0 and stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())