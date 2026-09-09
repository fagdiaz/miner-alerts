"""Backwards-compatibility facade for app.core.acquisition (Spec 041).

This module aliases app.core.acquisition directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.acquisition as _impl

from app.core.acquisition import *  # noqa: F401, F403

sys.modules[__name__] = _impl
