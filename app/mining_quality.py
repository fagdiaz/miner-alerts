"""Backwards-compatibility facade for app.core.mining_quality (Spec 041).

This module aliases app.core.mining_quality directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.mining_quality as _impl

from app.core.mining_quality import *  # noqa: F401, F403

sys.modules[__name__] = _impl
