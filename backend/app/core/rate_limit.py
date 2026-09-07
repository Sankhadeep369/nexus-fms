"""Lightweight in-memory, per-client rate limiting — no external dependencies.

The backend is a single process (one HF Space container), so an in-memory
sliding-window counter is sufficient. Client identity is best-effort: the
left-most X-Forwarded-For hop (set by the platform proxy) when present, else the
socket peer. Behind a shared proxy with no forwarded header this degrades to
global limiting; robust per-user limits need real auth tokens (not yet available).

Each call to `rate_limiter(...)` returns an independent FastAPI dependency with
its own counter, so different routes get independent budgets.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def _client_id(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def rate_limiter(max_requests: int, window_seconds: int = 60):
    hits: dict[str, deque] = defaultdict(deque)
    lock = threading.Lock()

    def dependency(request: Request) -> None:
        cid = _client_id(request)
        now = time.time()
        cutoff = now - window_seconds
        with lock:
            dq = hits[cid]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= max_requests:
                retry = int(dq[0] + window_seconds - now) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Please slow down and retry in {retry}s.",
                    headers={"Retry-After": str(retry)},
                )
            dq.append(now)
            # Bound memory: drop empty buckets once the map grows large.
            if len(hits) > 5000:
                for k in [k for k, v in hits.items() if not v]:
                    del hits[k]

    return dependency
