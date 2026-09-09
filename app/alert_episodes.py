"""Backwards-compatibility facade for app.core.alert_episodes (Spec 041).

This module aliases app.core.alert_episodes directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.alert_episodes as _impl

from app.core.alert_episodes import *  # noqa: F401, F403

sys.modules[__name__] = _impl
