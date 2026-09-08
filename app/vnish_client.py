from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

_LOGGER = logging.getLogger(__name__)

DEFAULT_HTTP_TIMEOUT = 2.5  # Seconds per request (R2 constraint)


def mask_secret(secret: Optional[str]) -> str:
    """Mask sensitive passwords or authentication tokens for safe logging."""
    if not secret:
        return "None"
    return "***"


def unlock_miner(
    host: str,
    password: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Authenticate against Vnish REST API and obtain session token.
    
    Returns: (success: bool, token: Optional[str], error_message: Optional[str])
    """
    url = f"http://{host}/api/v1/unlock"
    payload = {"pw": password}
    requester = session or requests
    try:
        resp = requester.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json()
                token = data.get("token")
                if token:
                    return True, str(token), None
                return False, None, "missing_token_in_response"
            except Exception as parse_err:
                return False, None, f"json_decode_error: {parse_err}"
        elif resp.status_code == 401:
            return False, None, "unauthorized_invalid_password"
        else:
            return False, None, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, None, "connection_timeout"
    except requests.exceptions.ConnectionError:
        return False, None, "connection_refused_or_offline"
    except Exception as exc:
        return False, None, f"request_error: {type(exc).__name__}"


def lock_miner(
    host: str,
    token: Optional[str],
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> bool:
    """
    Close authenticated session on Vnish miner.
    
    Returns: True if locked successfully or if token was empty.
    """
    if not token:
        return True
    url = f"http://{host}/api/v1/lock"
    headers = {"Authorization": f"Bearer {token}"}
    requester = session or requests
    try:
        resp = requester.post(url, headers=headers, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def get_cooling_settings(
    host: str,
    token: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Retrieve cooling settings from /api/v1/settings.
    
    Returns: (success: bool, cooling_dict: Optional[dict], error_message: Optional[str])
    """
    url = f"http://{host}/api/v1/settings"
    headers = {"Authorization": f"Bearer {token}"}
    requester = session or requests
    try:
        resp = requester.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            cooling = data.get("miner", {}).get("cooling")
            return True, cooling, None
        return False, None, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, None, "connection_timeout"
    except Exception as exc:
        return False, None, f"request_error: {type(exc).__name__}"


def set_manual_fan_duty(
    host: str,
    token: str,
    duty_percent: int,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Set fan speed duty cycle in manual mode.
    Duty is clamped between 40% (hardware minimum) and 100% (maximum).
    
    Returns: (success: bool, error_message: Optional[str])
    """
    clamped_duty = max(40, min(100, int(duty_percent)))
    url = f"http://{host}/api/v1/settings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "miner": {
            "cooling": {
                "mode": {
                    "name": "manual",
                    "param": clamped_duty,
                }
            }
        }
    }
    requester = session or requests
    try:
        resp = requester.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return True, None
        return False, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "connection_timeout"
    except Exception as exc:
        return False, f"request_error: {type(exc).__name__}"


def safe_set_fan_duty(
    host: str,
    password: str,
    duty_percent: int,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
) -> Tuple[bool, Optional[str]]:
    """
    High-level transactional helper:
    1. Authenticate (unlock)
    2. Modulate fan duty in manual mode
    3. Ensure session is locked in finally block
    
    Returns: (success: bool, error_message: Optional[str])
    """
    token = None
    try:
        ok, token, err = unlock_miner(host, password, timeout=timeout)
        if not ok or not token:
            return False, f"unlock_failed: {err}"
        return set_manual_fan_duty(host, token, duty_percent, timeout=timeout)
    finally:
        if token:
            try:
                lock_miner(host, token, timeout=timeout)
            except Exception:
                pass


def get_summary_cooling(
    host: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Read unauthenticated cooling summary from /api/v1/summary.
    
    Returns: (success: bool, cooling_dict: Optional[dict], error_message: Optional[str])
    """
    url = f"http://{host}/api/v1/summary"
    requester = session or requests
    try:
        resp = requester.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            cooling = data.get("miner", {}).get("cooling")
            return True, cooling, None
        return False, None, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, None, "connection_timeout"
    except Exception as exc:
        return False, None, f"request_error: {type(exc).__name__}"


# ---------------------------------------------------------------------------
# Spec 040: Dynamic Power & Preset Balancer API methods
# ---------------------------------------------------------------------------

def get_available_presets(
    host: str,
    token: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Retrieve list of available overclocking presets from /api/v1/presets.
    
    Returns: (success: bool, presets_list: Optional[list], error_message: Optional[str])
    """
    url = f"http://{host}/api/v1/presets"
    headers = {"Authorization": f"Bearer {token}"}
    requester = session or requests
    try:
        resp = requester.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return True, data, None
            elif isinstance(data, dict) and "presets" in data:
                return True, data["presets"], None
            return True, [], None
        return False, None, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, None, "connection_timeout"
    except Exception as exc:
        return False, None, f"request_error: {type(exc).__name__}"


def set_miner_preset(
    host: str,
    token: str,
    preset_name: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Update active overclocking preset on Vnish miner.
    
    Returns: (success: bool, error_message: Optional[str])
    """
    url = f"http://{host}/api/v1/settings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    clean_preset = str(preset_name).upper().rstrip("W").strip()
    payload = {
        "miner": {
            "overclock": {
                "preset": clean_preset
            }
        }
    }
    requester = session or requests
    try:
        resp = requester.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return True, None
        return False, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "connection_timeout"
    except Exception as exc:
        return False, f"request_error: {type(exc).__name__}"


def safe_set_miner_preset(
    host: str,
    password: str,
    preset_name: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
) -> Tuple[bool, Optional[str]]:
    """
    Transactional wrapper for preset change:
    1. Authenticate (unlock)
    2. Modulate overclock preset
    3. Ensure session is locked in finally block
    
    Returns: (success: bool, error_message: Optional[str])
    """
    token = None
    try:
        ok, token, err = unlock_miner(host, password, timeout=timeout)
        if not ok or not token:
            return False, f"unlock_failed: {err}"
        return set_miner_preset(host, token, preset_name, timeout=timeout)
    finally:
        if token:
            try:
                lock_miner(host, token, timeout=timeout)
            except Exception:
                pass


def get_overclock_settings(
    host: str,
    token: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Retrieve active overclock and preset switcher settings from /api/v1/settings.
    
    Returns: (success: bool, settings_dict: Optional[dict], error_message: Optional[str])
    where settings_dict contains:
      - 'preset': active preset (e.g. '2300')
      - 'switcher_enabled': bool
      - 'top_preset': top preset ceiling (e.g. '2700')
      - 'min_preset': bottom preset floor (e.g. '1740')
      - 'rise_temp': temperature threshold to step up
      - 'decrease_temp': temperature threshold to step down
      - 'check_time': evaluation interval seconds
      - 'target_power_w': inferred target power in Watts (from top_preset if switcher enabled, else preset)
      - 'raw': complete overclock sub-dict
    """
    url = f"http://{host}/api/v1/settings"
    headers = {"Authorization": f"Bearer {token}"}
    requester = session or requests
    try:
        resp = requester.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            overclock = data.get("miner", {}).get("overclock", {})
            preset_switcher = overclock.get("preset_switcher", {})
            active_preset = overclock.get("preset")
            switcher_enabled = bool(preset_switcher.get("enabled", False))
            top_preset = preset_switcher.get("top_preset")
            min_preset = preset_switcher.get("min_preset")
            rise_temp = preset_switcher.get("rise_temp")
            decrease_temp = preset_switcher.get("decrease_temp")
            check_time = preset_switcher.get("check_time")

            target_power_w = None
            if switcher_enabled and top_preset:
                try:
                    target_power_w = float(str(top_preset).upper().rstrip("W").strip())
                except (ValueError, TypeError):
                    pass
            if target_power_w is None and active_preset:
                try:
                    target_power_w = float(str(active_preset).upper().rstrip("W").strip())
                except (ValueError, TypeError):
                    pass

            result = {
                "preset": str(active_preset) if active_preset is not None else None,
                "switcher_enabled": switcher_enabled,
                "top_preset": str(top_preset) if top_preset is not None else None,
                "min_preset": str(min_preset) if min_preset is not None else None,
                "rise_temp": rise_temp,
                "decrease_temp": decrease_temp,
                "check_time": check_time,
                "target_power_w": target_power_w,
                "raw": overclock,
            }
            return True, result, None
        return False, None, f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, None, "connection_timeout"
    except Exception as exc:
        return False, None, f"request_error: {type(exc).__name__}"


def safe_get_overclock_settings(
    host: str,
    password: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Transactional wrapper for retrieving overclock settings:
    1. Authenticate (unlock)
    2. Read overclock settings
    3. Ensure session is locked in finally block
    
    Returns: (success: bool, settings_dict: Optional[dict], error_message: Optional[str])
    """
    token = None
    try:
        ok, token, err = unlock_miner(host, password, timeout=timeout)
        if not ok or not token:
            return False, None, f"unlock_failed: {err}"
        return get_overclock_settings(host, token, timeout=timeout)
    finally:
        if token:
            try:
                lock_miner(host, token, timeout=timeout)
            except Exception:
                pass


