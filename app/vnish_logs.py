"""Backwards-compatibility facade for app.vnish.logs (Spec 041).

This module aliases app.vnish.logs directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.vnish.logs as _impl

from app.vnish.logs import *  # noqa: F401, F403

sys.modules[__name__] = _impl
