"""Configurable retry with exponential backoff for async operations."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger("sams.retry")


@dataclass
class RetryOptions:
    """Controls how many times and how often a failed async operation is retried."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay: float = 60.0

    @classmethod
    def from_dict(cls, d: dict) -> "RetryOptions":
        return cls(
            max_attempts=int(d.get("max_attempts", 3)),
            initial_delay=float(d.get("initial_delay", 1.0)),
            backoff_multiplier=float(d.get("backoff_multiplier", 2.0)),
            max_delay=float(d.get("max_delay", 60.0)),
        )

    def to_dict(self) -> dict:
        return {
            "max_attempts": self.max_attempts,
            "initial_delay": self.initial_delay,
            "backoff_multiplier": self.backoff_multiplier,
            "max_delay": self.max_delay,
        }


async def async_retry(
    fn: Callable[[], Any],
    opts: RetryOptions,
    on_retry: Callable[[int, float, Exception], Any] | None = None,
) -> Any:
    """Call fn up to opts.max_attempts times with exponential backoff between failures.

    asyncio.CancelledError is never retried and always propagates immediately.
    All other exceptions trigger a retry until max_attempts is exhausted.
    on_retry(attempt, delay, exc) is awaited before each sleep (if provided).
    """
    if opts.max_attempts <= 0:
        raise ValueError("max_attempts must be >= 1")
    delay = opts.initial_delay
    last_exc: Exception | None = None
    for attempt in range(1, opts.max_attempts + 1):
        try:
            return await fn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt >= opts.max_attempts:
                break
            if on_retry is not None:
                try:
                    await on_retry(attempt, delay, exc)
                except Exception:
                    pass
            log.warning("retry %d/%d in %.1fs: %s", attempt, opts.max_attempts, delay, exc)
            await asyncio.sleep(delay)
            delay = min(delay * opts.backoff_multiplier, opts.max_delay)
    raise last_exc  # type: ignore[misc]
