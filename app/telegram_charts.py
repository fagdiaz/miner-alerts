"""Backwards-compatibility facade for app.telegram.charts (Spec 041).

This module aliases app.telegram.charts directly so that legacy imports,
introspection, and unittest patches continue to target the real implementation.
"""

from __future__ import annotations

import sys
import app.telegram.charts as _impl

from app.telegram.charts import *  # noqa: F401, F403
from app.telegram.charts import _connect_ro  # noqa: F401

sys.modules[__name__] = _impl
