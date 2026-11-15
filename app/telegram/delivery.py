"""Bounded, at-least-once sendMessage transport; never retries miner actions."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

import requests


def post_message(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    *,
    log: Callable[[str], None],
    heartbeat: Callable[[], None] = lambda: None,
    timeout: tuple[float, float] = (2.0, 6.0),
) -> Optional[requests.Response]:
    """Confirm Telegram ok=true, retry transient failures at most twice.

    A lost response can cause a duplicate. Never retry permanent errors, nor
    retry a rate limit earlier than requested. No message contents are logged.
    """
    for attempt in range(1, 4):
        heartbeat()
        delay = float(attempt)
        retryable = False
        response = None
        outcome = "unknown"
        try:
            response = session.post(url, json=payload, timeout=timeout)
            outcome = f"http_{response.status_code}"
            try:
                body = response.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                body = {}
            if response.status_code == 200 and body.get("ok") is True:
                heartbeat()
                return response
            code = body.get("error_code", response.status_code)
            retryable = response.status_code >= 500 or code == 429
            if code == 429:
                try:
                    delay = float(body.get("parameters", {}).get("retry_after", 1))
                except (TypeError, ValueError, AttributeError):
                    delay = 1.0
                # Do not block the only sender for an unbounded rate limit.
                if not 0 <= delay <= 30:
                    retryable = False
        except (requests.ConnectionError, requests.Timeout) as exc:
            outcome = type(exc).__name__
            retryable = True
        finally:
            heartbeat()
        if not retryable or attempt == 3:
            log(f"TG DELIVERY_FAILED attempts={attempt} outcome={outcome}")
            return None
        log(f"TG RETRY attempt={attempt} outcome={outcome} delay_s={delay:g}")
        # Keep liveness current even during a rate-limit wait.
        remaining = delay
        while remaining > 0:
            pause = min(remaining, 5.0)
            time.sleep(pause)
            heartbeat()
            remaining -= pause
    return None
