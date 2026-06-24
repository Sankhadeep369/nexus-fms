"""Seeds the response cache with hand-written answers for the curated suggestion
list (`app/core/suggestions.py`) so the UI's quick-suggestion chips and `/` picker
answer instantly, without waiting on CPU generation.

Usage (from 08_rag_app/backend, with the venv active):
    python -m scripts.seed_suggestion_cache
"""

from app.core.cache import get_response_cache
from app.core.suggestion_answers import SUGGESTED_ANSWERS
from app.core.suggestions import SUGGESTED_QUESTIONS


def main() -> None:
    cache = get_response_cache()
    for query in SUGGESTED_QUESTIONS:
        answer = SUGGESTED_ANSWERS.get(query)
        if answer is None:
            print(f"WARNING: no hand-written answer for: {query}")
            continue
        cache.set(query, "simple", {"answer": answer, "retrieved_sources": []})
        print(f"seeded: {query}")


if __name__ == "__main__":
    main()
