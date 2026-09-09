"""Backwards-compatibility facade for app.telegram.messages (Spec 041).

This module aliases app.telegram.messages directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.telegram.messages as _impl

from app.telegram.messages import *  # noqa: F401, F403

sys.modules[__name__] = _impl
