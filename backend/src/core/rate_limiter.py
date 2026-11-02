import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status


class SimpleRateLimiter:
    """Limitador de tasa en memoria por ventana deslizante (sliding window).

    Diseñado para proteger endpoints sensibles contra abuso y ataques de denegación de servicio.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        detail: str = "Demasiadas solicitudes. Por favor, intentá nuevamente más tarde.",
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.detail = detail
        self._records: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            timestamps = self._records[key]
            cutoff = now - self.window_seconds
            valid_timestamps = [t for t in timestamps if t > cutoff]
            if len(valid_timestamps) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=self.detail,
                )
            valid_timestamps.append(now)
            self._records[key] = valid_timestamps

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
