"""Backwards-compatibility facade for app.core.restart_intelligence (Spec 041).

This module aliases app.core.restart_intelligence directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.restart_intelligence as _impl

from app.core.restart_intelligence import *  # noqa: F401, F403

sys.modules[__name__] = _impl
