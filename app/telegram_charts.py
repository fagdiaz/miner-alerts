"""Backwards-compatibility facade for app.telegram.charts (Spec 041).

This module re-exports all symbols from app.telegram.charts to ensure
legacy imports in tests and external tools continue working without changes.
"""

from __future__ import annotations

from app.telegram.charts import *  # noqa: F401, F403
from app.telegram.charts import _connect_ro  # noqa: F401
