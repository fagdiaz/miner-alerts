"""Backwards-compatibility facade for app.core.stability_profile (Spec 041).

This module aliases app.core.stability_profile directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.stability_profile as _impl

from app.core.stability_profile import *  # noqa: F401, F403

sys.modules[__name__] = _impl
