"""Warms the response cache for the curated suggestion list (`app/core/suggestions.py`)
so the UI's quick-suggestion chips and `/` picker answer instantly.

Calls the running backend's own `/chat` endpoint (in "simple" mode) for each question
that isn't cached yet, so generation reuses the already-loaded model instead of
spinning up a second copy.

Usage (from 08_rag_app/backend, with the venv active, backend already running):
    python -m scripts.pregenerate_suggestions [--base-url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

from app.core.cache import get_response_cache
from app.core.suggestions import SUGGESTED_QUESTIONS


def warm(base_url: str, query: str) -> None:
    req = urllib.request.Request(
        f"{base_url}/chat",
        data=json.dumps({"query": query, "mode": "simple"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=1800) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: "):])
            if payload["type"] == "done":
                return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    cache = get_response_cache()
    total = len(SUGGESTED_QUESTIONS)
    for i, query in enumerate(SUGGESTED_QUESTIONS, 1):
        if cache.get(query, "simple") is not None:
            print(f"[{i}/{total}] already cached: {query}")
            continue
        print(f"[{i}/{total}] generating: {query}")
        t0 = time.time()
        warm(args.base_url, query)
        print(f"[{i}/{total}] done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
