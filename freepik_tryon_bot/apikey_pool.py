"""Round-robin API key pool with auto-disable on auth/quota errors.

Used for transparent rotation across multiple Freepik API keys so that when
one key is exhausted or rate-limited the bot keeps working on the next one.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _KeyState:
    key: str
    disabled_until: float = 0.0
    permanently_disabled: bool = False
    failures: int = 0
    last_used: float = field(default=0.0)


class APIKeyPool:
    """In-memory rotation pool. Thread-safe; works under asyncio.to_thread too."""

    def __init__(self, keys: list[str] | tuple[str, ...]) -> None:
        if not keys:
            raise ValueError("API key pool butuh minimal 1 key")
        self._states: list[_KeyState] = [_KeyState(key=k) for k in keys]
        self._lock = threading.Lock()
        self._index = 0

    def __len__(self) -> int:
        return len(self._states)

    def _is_available(self, state: _KeyState, now: float) -> bool:
        if state.permanently_disabled:
            return False
        return state.disabled_until <= now

    def lease(self) -> str | None:
        """Return next available key, or ``None`` if all are disabled."""
        with self._lock:
            now = time.time()
            n = len(self._states)
            for offset in range(n):
                idx = (self._index + offset) % n
                state = self._states[idx]
                if self._is_available(state, now):
                    state.last_used = now
                    self._index = (idx + 1) % n
                    return state.key
            return None

    def report_failure(
        self,
        key: str,
        *,
        permanent: bool = False,
        cooldown_seconds: float = 60.0,
    ) -> None:
        """Mark ``key`` as failed.

        ``permanent=True`` is for 401/403 (invalid key); transient errors get
        a short cooldown so the next request lands on a different key.
        """
        with self._lock:
            for state in self._states:
                if state.key != key:
                    continue
                state.failures += 1
                if permanent:
                    state.permanently_disabled = True
                    logger.warning(
                        "API key dimatikan permanen setelah %d kegagalan",
                        state.failures,
                    )
                else:
                    state.disabled_until = max(state.disabled_until, time.time() + cooldown_seconds)
                    logger.info(
                        "API key di-cooldown %.0fs (kegagalan ke-%d)",
                        cooldown_seconds,
                        state.failures,
                    )
                break

    def report_success(self, key: str) -> None:
        with self._lock:
            for state in self._states:
                if state.key == key:
                    state.failures = 0
                    state.disabled_until = 0.0
                    return

    def status(self) -> list[dict[str, object]]:
        with self._lock:
            now = time.time()
            return [
                {
                    "index": i,
                    "fingerprint": _fingerprint(state.key),
                    "available": self._is_available(state, now),
                    "permanent": state.permanently_disabled,
                    "cooldown_remaining": max(0.0, state.disabled_until - now),
                    "failures": state.failures,
                }
                for i, state in enumerate(self._states)
            ]


def _fingerprint(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}…{key[-4:]}"
