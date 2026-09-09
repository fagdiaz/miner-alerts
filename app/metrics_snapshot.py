"""Backwards-compatibility facade for app.core.metrics_snapshot (Spec 041).

This module aliases app.core.metrics_snapshot directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.metrics_snapshot as _impl

from app.core.metrics_snapshot import *  # noqa: F401, F403

sys.modules[__name__] = _impl
