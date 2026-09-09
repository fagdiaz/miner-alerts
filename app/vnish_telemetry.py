"""Backwards-compatibility facade for app.vnish.telemetry (Spec 041).

This module aliases app.vnish.telemetry directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.vnish.telemetry as _impl

from app.vnish.telemetry import *  # noqa: F401, F403

sys.modules[__name__] = _impl
