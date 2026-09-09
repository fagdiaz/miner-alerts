"""Backwards-compatibility facade for app.governance.energy_efficiency (Spec 041).

This module aliases app.governance.energy_efficiency directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.governance.energy_efficiency as _impl

from app.governance.energy_efficiency import *  # noqa: F401, F403

sys.modules[__name__] = _impl
