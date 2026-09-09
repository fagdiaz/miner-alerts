"""Backwards-compatibility facade for app.governance.fan_health (Spec 041).

This module aliases app.governance.fan_health directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.governance.fan_health as _impl

from app.governance.fan_health import *  # noqa: F401, F403

sys.modules[__name__] = _impl
