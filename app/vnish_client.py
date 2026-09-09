"""Backwards-compatibility facade for app.vnish.client (Spec 041).

This module aliases app.vnish.client directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.vnish.client as _impl

# Re-export symbols for static analyzers
from app.vnish.client import *  # noqa: F401, F403

# Module aliasing for unittest.mock.patch compatibility
sys.modules[__name__] = _impl
