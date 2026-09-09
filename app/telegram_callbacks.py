"""Backwards-compatibility facade for app.telegram.callbacks (Spec 041).

This module aliases app.telegram.callbacks directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.telegram.callbacks as _impl

from app.telegram.callbacks import *  # noqa: F401, F403

sys.modules[__name__] = _impl
