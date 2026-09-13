"""Asynchronous / Non-blocking Collector for Vnish Chain Telemetry (Spec 054).

Fetches /api/v1/chains endpoint per miner or across the entire fleet
with bounded timeouts (default 2.5s) without blocking the monitoring loop.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple

import requests

from app.vnish.chains import ChainTelemetry
from app.vnish.client import DEFAULT_HTTP_TIMEOUT

_LOGGER = logging.getLogger(__name__)


def fetch_miner_chains(
    host: str,
    token: Optional[str] = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, List[ChainTelemetry], Optional[str]]:
    """Fetch and parse /api/v1/chains from a single Vnish miner.

    Returns:
        (success: bool, chains: List[ChainTelemetry], error_message: Optional[str])
    """
    url = f"http://{host}/api/v1/chains"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    requester = session or requests
    try:
        resp = requester.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json()
                if not isinstance(data, list):
                    return False, [], f"invalid_response_format_expected_list:{type(data).__name__}"
                chains = [
                    ChainTelemetry.from_api_dict(item)
                    for item in data
                    if isinstance(item, dict)
                ]
                return True, chains, None
            except Exception as parse_err:
                return False, [], f"json_decode_error:{parse_err}"
        elif resp.status_code == 401:
            return False, [], "unauthorized_invalid_token"
        else:
            return False, [], f"http_status_{resp.status_code}"
    except requests.exceptions.Timeout:
        return False, [], "connection_timeout"
    except requests.exceptions.ConnectionError:
        return False, [], "connection_refused_or_offline"
    except Exception as exc:
        return False, [], f"request_error:{type(exc).__name__}"


def fetch_fleet_chains(
    miner_hosts: Mapping[str, str],
    token: Optional[str] = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    max_workers: int = 4,
) -> Dict[str, Tuple[bool, List[ChainTelemetry], Optional[str]]]:
    """Fetch /api/v1/chains in parallel across multiple miners using ThreadPoolExecutor.

    Args:
        miner_hosts: Mapping of miner identifier (e.g. key or name) to host IP/hostname.
        token: Optional auth token.
        timeout: Maximum seconds to wait per request.
        max_workers: Max concurrent threads.

    Returns:
        Mapping of miner identifier to (success, chains_list, error_message).
    """
    results: Dict[str, Tuple[bool, List[ChainTelemetry], Optional[str]]] = {}
    if not miner_hosts:
        return results

    pool_size = max(1, min(max_workers, len(miner_hosts)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as pool:
        future_to_key = {
            pool.submit(fetch_miner_chains, host, token=token, timeout=timeout): key
            for key, host in miner_hosts.items()
        }
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            try:
                res = future.result()
                results[key] = res
            except Exception as exc:
                results[key] = (False, [], f"pool_execution_error:{type(exc).__name__}")

    return results
