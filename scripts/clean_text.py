#!/usr/bin/env python3
"""
clean_text.py

Reads all .txt files from a source directory (typically the output of
extract_pdf_text.py), cleans common PDF-extraction artifacts, and writes
the cleaned files into an output directory, preserving the original
folder structure.

Cleaning steps applied to each file:
    1. Split the file into "pages" using "--- Page N ---" markers (if
       present, e.g. from extract_pdf_text.py) so header/footer detection
       can work per-page.
    2. Detect and remove repeated headers/footers: lines that recur near
       the top or bottom of a large fraction of pages (e.g. document
       titles, chapter names, "Confidential", company names, etc.).
    3. Strip standalone page-number lines ("12", "Page 12", "12 of 40",
       "- 12 -", roman numerals, etc.).
    4. Strip common PDF artifacts (form-feed characters, lone bullet/
       control characters, long runs of dashes/underscores/dots used as
       separators, stray page-marker lines).
    5. Normalize whitespace: trim trailing spaces, collapse runs of
       spaces/tabs, remove blank-line runs greater than one - while still
       preserving paragraph breaks (a single blank line between
       paragraphs is kept).

Usage:
    python clean_text.py
    python clean_text.py --source extracted_text --output cleaned_text
    python clean_text.py --overwrite --verbose

Notes:
    - Header/footer detection is heuristic and per-file: it only removes
      lines that repeat across multiple pages of the *same* document, so
      it won't strip content that's simply short or coincidentally
      similar between unrelated files.
    - No external dependencies are required; only the standard library.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from collections import Counter
from pathlib import Path

LOG_FILE_NAME = "clean_text.log"

# Marker inserted by extract_pdf_text.py between pages, e.g. "--- Page 3 ---"
PAGE_MARKER_RE = re.compile(r"^-{3,}\s*Page\s+\d+\s*-{3,}$", re.IGNORECASE)

# Standalone page-number-like lines: "12", "Page 12", "12 of 40", "- 12 -",
# "p. 12", roman numerals such as "iv" / "XII" on their own line, etc.
PAGE_NUMBER_PATTERNS = [
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^page\s+\d{1,4}$", re.IGNORECASE),
    re.compile(r"^page\s+\d{1,4}\s+of\s+\d{1,4}$", re.IGNORECASE),
    re.compile(r"^\d{1,4}\s+of\s+\d{1,4}$", re.IGNORECASE),
    re.compile(r"^[-–—]\s*\d{1,4}\s*[-–—]$"),
    re.compile(r"^p\.?\s*\d{1,4}$", re.IGNORECASE),
    re.compile(r"^[ivxlcdm]{1,8}$", re.IGNORECASE),  # roman numerals alone
]

# Lines that are pure decorative separators / artifacts, e.g. "----------",
# "________", "........", "* * * * *", form-feed leftovers, etc.
SEPARATOR_LINE_RE = re.compile(r"^[\s\-_=~*.•·]{3,}$")

# Control / non-printable characters PDF extraction sometimes leaves behind
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Header/footer heuristic tuning
HEADER_FOOTER_ZONE_LINES = 2       # how many lines from top/bottom of a page to inspect
HEADER_FOOTER_MIN_PAGES = 3        # need at least this many pages to bother detecting
HEADER_FOOTER_MIN_FRACTION = 0.5   # a line must repeat on >= this fraction of pages
HEADER_FOOTER_MIN_LEN = 3          # ignore very short lines (e.g. "1", "-") for this check


def setup_logging(output_dir: Path, verbose: bool) -> logging.Logger:
    """Configure logging to both console and a log file inside output_dir."""
    logger = logging.getLogger("clean_text")
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


def split_into_pages(raw_text: str) -> list[str]:
    """
    Split raw text into a list of per-page strings using "--- Page N ---"
    markers if present. If no markers are found, the whole text is
    treated as a single page.
    """
    lines = raw_text.splitlines()
    pages: list[list[str]] = []
    current: list[str] = []
    found_marker = False

    for line in lines:
        if PAGE_MARKER_RE.match(line.strip()):
            found_marker = True
            if current:
                pages.append(current)
            current = []
            continue
        current.append(line)

    if current:
        pages.append(current)

    if not found_marker:
        return ["\n".join(lines)]

    return ["\n".join(page_lines) for page_lines in pages]


def detect_repeated_header_footer_lines(pages: list[str]) -> set[str]:
    """
    Identify lines that repeat near the top or bottom of many pages,
    which are typically running headers/footers rather than content.

    Returns a set of exact (stripped) line strings to remove wherever
    they occur in the document.
    """
    if len(pages) < HEADER_FOOTER_MIN_PAGES:
        return set()

    zone_counter: Counter[str] = Counter()

    for page_text in pages:
        page_lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
        if not page_lines:
            continue

        top_zone = page_lines[:HEADER_FOOTER_ZONE_LINES]
        bottom_zone = page_lines[-HEADER_FOOTER_ZONE_LINES:]

        seen_this_page = set(top_zone) | set(bottom_zone)
        for line in seen_this_page:
            if len(line) >= HEADER_FOOTER_MIN_LEN:
                zone_counter[line] += 1

    threshold = max(HEADER_FOOTER_MIN_PAGES, int(len(pages) * HEADER_FOOTER_MIN_FRACTION))
    repeated = {line for line, count in zone_counter.items() if count >= threshold}
    return repeated


def is_page_number_line(stripped_line: str) -> bool:
    return any(pattern.match(stripped_line) for pattern in PAGE_NUMBER_PATTERNS)


def clean_page_text(page_text: str, header_footer_lines: set[str]) -> list[str]:
    """
    Clean a single page's text and return the resulting list of kept
    lines (artifacts, headers/footers, and page numbers removed).
    """
    kept_lines: list[str] = []

    for raw_line in page_text.splitlines():
        line = CONTROL_CHARS_RE.sub("", raw_line)
        stripped = line.strip()

        if not stripped:
            kept_lines.append("")  # preserve as a potential paragraph break
            continue

        if stripped in header_footer_lines:
            continue

        if is_page_number_line(stripped):
            continue

        if SEPARATOR_LINE_RE.match(stripped):
            continue

        if PAGE_MARKER_RE.match(stripped):
            continue

        # Collapse internal runs of whitespace/tabs to a single space
        normalized = re.sub(r"[ \t]+", " ", stripped)
        kept_lines.append(normalized)

    return kept_lines


def collapse_blank_lines(lines: list[str]) -> str:
    """
    Collapse 2+ consecutive blank lines into exactly one blank line
    (a paragraph separator), and strip leading/trailing blank lines.
    """
    result: list[str] = []
    previous_blank = False

    for line in lines:
        is_blank = (line.strip() == "")
        if is_blank and previous_blank:
            continue
        result.append(line)
        previous_blank = is_blank

    # Strip leading/trailing blank lines
    while result and result[0].strip() == "":
        result.pop(0)
    while result and result[-1].strip() == "":
        result.pop()

    return "\n".join(result) + "\n"


def clean_text(raw_text: str) -> str:
    """Full cleaning pipeline for one document's raw extracted text."""
    pages = split_into_pages(raw_text)
    header_footer_lines = detect_repeated_header_footer_lines(pages)

    all_lines: list[str] = []
    for page_text in pages:
        page_lines = clean_page_text(page_text, header_footer_lines)
        all_lines.extend(page_lines)
        all_lines.append("")  # blank line between pages -> becomes paragraph gap

    return collapse_blank_lines(all_lines)


def process_directory(
    source_dir: Path,
    output_dir: Path,
    logger: logging.Logger,
    overwrite: bool = False,
) -> dict:
    """
    Walk source_dir for .txt files and write cleaned versions to
    output_dir, preserving relative subfolder structure.
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
        output_path = output_dir / relative_path

        logger.debug("(%d/%d) Processing: %s", index, stats["total"], relative_path)

        if output_path.exists() and not overwrite:
            logger.info(
                "(%d/%d) SKIP (already exists): %s", index, stats["total"], relative_path
            )
            stats["skipped"] += 1
            continue

        try:
            raw_text = txt_path.read_text(encoding="utf-8", errors="replace")
            cleaned = clean_text(raw_text)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(cleaned, encoding="utf-8")

            if not cleaned.strip():
                logger.warning(
                    "(%d/%d) Cleaned file is empty: %s", index, stats["total"], relative_path
                )

            logger.info(
                "(%d/%d) OK: %s -> %s", index, stats["total"], relative_path, output_path
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
        description="Clean extracted PDF text: remove repeated headers/footers, "
        "page numbers, PDF artifacts, and excessive whitespace, while "
        "preserving paragraphs and folder structure."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("extracted_text"),
        help="Root folder containing .txt files to clean (default: extracted_text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("cleaned_text"),
        help="Root folder to write cleaned .txt files to (default: cleaned_text)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing cleaned files instead of skipping them",
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

    if stats["total"] > 0 and stats["succeeded"] == 0 and stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())