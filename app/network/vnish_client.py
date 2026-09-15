from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.vnish.client import (
    DEFAULT_HTTP_TIMEOUT,
    get_available_presets,
    get_cooling_settings,
    get_miner_status,
    get_overclock_settings,
    get_summary_cooling,
    lock_miner,
    mask_secret,
    parse_miner_status_flags,
    restart_mining,
    resume_mining,
    safe_get_overclock_settings,
    safe_restart_mining,
    safe_resume_mining,
    safe_set_fan_duty,
    safe_set_miner_preset,
    safe_stop_mining,
    set_manual_fan_duty,
    set_miner_preset,
    stop_mining,
    unlock_miner,
)

# Alias for convenience
set_fan_duty = set_manual_fan_duty

_LOGGER = logging.getLogger(__name__)


class VnishClient:
    """
    Object-oriented client for the Vnish ASIC REST API (port 80 HTTP).
    
    Encapsulates bearer token authentication, session reuse, bounded timeouts (2.5s),
    and safe state transitions for fan governance, overclock presets, and mining restarts.
    """

    def __init__(
        self,
        host: str,
        password: str,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.host = host
        self.password = password
        self.timeout = timeout
        self._session = session or requests.Session()
        self._token: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        return self._token

    def unlock(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Authenticate against Vnish API and retain session token."""
        ok, token, err = unlock_miner(
            host=self.host,
            password=self.password,
            timeout=self.timeout,
            session=self._session,
        )
        if ok and token:
            self._token = token
        return ok, token, err

    def lock(self) -> bool:
        """Explicitly lock and terminate the authenticated session."""
        if not self._token:
            return True
        ok = lock_miner(
            host=self.host,
            token=self._token,
            timeout=self.timeout,
            session=self._session,
        )
        self._token = None
        return ok

    def get_cooling_settings(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Retrieve cooling settings dictionary."""
        if not self._token:
            ok, _, err = self.unlock()
            if not ok:
                return False, None, f"unlock_failed: {err}"
        return get_cooling_settings(
            host=self.host,
            token=self._token or "",
            timeout=self.timeout,
            session=self._session,
        )

    def set_fan_duty(self, duty: int) -> Tuple[bool, Optional[str]]:
        """Safely set manual fan duty percentage (auto-unlocks and locks)."""
        return safe_set_fan_duty(
            host=self.host,
            password=self.password,
            fan_duty=duty,
            timeout=self.timeout,
            session=self._session,
        )

    def restart_mining(self) -> Tuple[bool, Optional[str]]:
        """Safely issue a soft mining restart (auto-unlocks and locks)."""
        return safe_restart_mining(
            host=self.host,
            password=self.password,
            timeout=self.timeout,
            session=self._session,
        )

    def get_status(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Retrieve miner status flags and telemetry."""
        if not self._token:
            ok, _, err = self.unlock()
            if not ok:
                return False, None, f"unlock_failed: {err}"
        return get_miner_status(
            host=self.host,
            token=self._token or "",
            timeout=self.timeout,
            session=self._session,
        )

    def get_overclock_settings(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Safely query active overclock preset and target power."""
        return safe_get_overclock_settings(
            host=self.host,
            password=self.password,
            timeout=self.timeout,
            session=self._session,
        )

    def set_preset(self, preset_name: str) -> Tuple[bool, Optional[str]]:
        """Safely configure an overclock preset by name."""
        return safe_set_miner_preset(
            host=self.host,
            password=self.password,
            preset_name=preset_name,
            timeout=self.timeout,
            session=self._session,
        )

    def __enter__(self) -> "VnishClient":
        self.unlock()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.lock()
