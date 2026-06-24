import hashlib
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.core.config import settings


class ResponseCache(ABC):
    """Storage-agnostic cache interface so the local diskcache implementation can later
    be swapped for a shared deployment cache (e.g. Redis) without touching the pipeline."""

    @abstractmethod
    def get(self, query: str, mode: str) -> Any | None: ...

    @abstractmethod
    def set(self, query: str, mode: str, value: Any) -> None: ...


class DiskResponseCache(ResponseCache):
    """SQLite-backed cache via diskcache, keyed by a hash of the normalized query and mode."""

    def __init__(self, directory, ttl: int):
        import diskcache

        self._cache = diskcache.Cache(str(directory))
        self._ttl = ttl

    @staticmethod
    def _hash(query: str, mode: str) -> str:
        return hashlib.sha256(f"{mode}:{query.strip().lower()}".encode("utf-8")).hexdigest()

    def get(self, query: str, mode: str) -> Any | None:
        return self._cache.get(self._hash(query, mode))

    def set(self, query: str, mode: str, value: Any) -> None:
        self._cache.set(self._hash(query, mode), value, expire=self._ttl)


@lru_cache(maxsize=1)
def get_response_cache() -> ResponseCache:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    return DiskResponseCache(directory=settings.cache_dir, ttl=settings.cache_ttl_seconds)
