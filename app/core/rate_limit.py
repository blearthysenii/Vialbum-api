from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def public_auth_rate_limit(
    *, limit: int = 60, window_seconds: int = 60
) -> Callable[[Request], None]:
    def check(request: Request) -> None:
        host = request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{host}"
        now = monotonic()
        with _lock:
            attempts = _attempts[key]
            while attempts and attempts[0] <= now - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Try again shortly.",
                )
            attempts.append(now)

    return check
