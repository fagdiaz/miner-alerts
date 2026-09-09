"""Backwards-compatibility facade for app.core.liveness (Spec 041).

This module aliases app.core.liveness directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.liveness as _impl

from app.core.liveness import *  # noqa: F401, F403

sys.modules[__name__] = _impl
