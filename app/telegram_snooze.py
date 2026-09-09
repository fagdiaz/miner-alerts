"""Backwards-compatibility facade for app.telegram.snooze (Spec 041).

This module re-exports all symbols from app.telegram.snooze to ensure
legacy imports in tests and external tools continue working without changes.
"""

from __future__ import annotations

from app.telegram.snooze import *  # noqa: F401, F403
