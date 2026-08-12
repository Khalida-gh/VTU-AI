#!/usr/bin/env python3
"""
test_ollama.py

Connects to a local Ollama server using the official `ollama` Python
package, sends a test prompt to the qwen2.5:7b model, and prints only
the model's response. Connection and model errors are handled
gracefully.

Usage:
    python test_ollama.py

Requirements:
    pip install ollama
    ollama pull qwen2.5:7b
    ollama serve   (if the server isn't already running)
"""

import sys

MODEL_NAME = "qwen2.5:7b"
PROMPT = "What is Software Engineering?"


def main() -> int:
    try:
        import ollama
    except ImportError:
        print(
            "Error: the 'ollama' package is not installed. Install it with:\n"
            "    pip install ollama",
            file=sys.stderr,
        )
        return 1

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": PROMPT}],
        )
    except ConnectionError:
        print(
            "Error: could not connect to the Ollama server. "
            "Make sure it's running locally (try: ollama serve).",
            file=sys.stderr,
        )
        return 1
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            print(
                f"Error: model '{MODEL_NAME}' was not found. "
                f"Pull it with: ollama pull {MODEL_NAME}",
                file=sys.stderr,
            )
        else:
            print(f"Error: Ollama returned an error: {exc.error}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: unexpected failure while contacting Ollama: {exc}", file=sys.stderr)
        return 1

    content = response.get("message", {}).get("content", "").strip()

    if not content:
        print("Error: received an empty response from the model.", file=sys.stderr)
        return 1

    print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())