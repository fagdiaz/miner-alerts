"""Backwards-compatibility facade for app.governance.preset_balancer (Spec 041).

This module aliases app.governance.preset_balancer directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.governance.preset_balancer as _impl

from app.governance.preset_balancer import *  # noqa: F401, F403

sys.modules[__name__] = _impl
