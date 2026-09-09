"""Backwards-compatibility facade for app.core.evidence_fusion (Spec 041).

This module aliases app.core.evidence_fusion directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.core.evidence_fusion as _impl

from app.core.evidence_fusion import *  # noqa: F401, F403

sys.modules[__name__] = _impl
