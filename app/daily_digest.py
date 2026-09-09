"""Backwards-compatibility facade for app.telegram.daily_digest (Spec 041).

This module aliases app.telegram.daily_digest directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.telegram.daily_digest as _impl

from app.telegram.daily_digest import *  # noqa: F401, F403

sys.modules[__name__] = _impl
