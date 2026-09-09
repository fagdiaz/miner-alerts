"""Backwards-compatibility facade for app.core.reboot_safety (Spec 041).

This module aliases app.core.reboot_safety directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.reboot_safety as _impl

from app.core.reboot_safety import *  # noqa: F401, F403

sys.modules[__name__] = _impl
