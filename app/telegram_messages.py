"""Backwards-compatibility facade for app.telegram.messages (Spec 041).

This module re-exports all symbols from app.telegram.messages to ensure
legacy imports in tests and external tools continue working without changes.
"""

from __future__ import annotations

from app.telegram.messages import *  # noqa: F401, F403
