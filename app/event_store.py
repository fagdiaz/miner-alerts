"""Backwards-compatibility facade for app.core.event_store (Spec 041).

This module aliases app.core.event_store directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.event_store as _impl

from app.core.event_store import *  # noqa: F401, F403

sys.modules[__name__] = _impl
