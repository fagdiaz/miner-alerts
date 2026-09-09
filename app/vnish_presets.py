"""Backwards-compatibility facade for app.vnish.presets (Spec 041).

This module aliases app.vnish.presets directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.vnish.presets as _impl

from app.vnish.presets import *  # noqa: F401, F403

sys.modules[__name__] = _impl
