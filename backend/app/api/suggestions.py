from fastapi import APIRouter

from app.core.cache import get_response_cache
from app.core.suggestions import SUGGESTED_QUESTIONS, SUGGESTION_CATEGORIES

router = APIRouter(tags=["suggestions"])


@router.get("/suggestions")
def suggestions() -> list[dict]:
    cache = get_response_cache()
    return [
        {
            "text": q,
            "cached": cache.get(q, "simple") is not None,
            "category": SUGGESTION_CATEGORIES.get(q, "General"),
        }
        for q in SUGGESTED_QUESTIONS
    ]
