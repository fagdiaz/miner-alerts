from __future__ import annotations

import json
import logging
import socket
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

_LOGGER = logging.getLogger(__name__)

# Fallback logger that formats like the monitor's log() function if no handler is installed
def _log_warn(msg: str) -> None:
    _LOGGER.warning(msg)


class CGMinerClient:
    """
    Object-oriented client for CGMiner / Antminer API (TCP port 4028).
    
    Provides high-level typed querying with socket timeouts, null-byte stripping,
    and defensive JSON parsing.
    """

    def __init__(self, host: str, port: int = 4028, default_timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.default_timeout = default_timeout

    def query(
        self,
        command: Union[str, bytes],
        parameter: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[dict]:
        """Send a command over TCP 4028 and return parsed response dictionary."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return query_cgminer(
            host=self.host,
            port=self.port,
            command=command,
            parameter=parameter,
            timeout=effective_timeout,
        )

    def summary(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[int], bool, Optional[dict]]:
        """Query 'summary' endpoint returning (rate_ths, elapsed, responded, raw_dict)."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return read_summary(self.host, self.port, timeout=effective_timeout)

    def stats_snapshot(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[Optional[int], bool, Optional[dict]]:
        """Query 'stats' endpoint returning (active_boards, responded, raw_dict)."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return read_stats_snapshot(self.host, self.port, timeout=effective_timeout)

    def active_boards(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[Optional[int], bool]:
        """Query 'stats' endpoint returning (active_boards, responded)."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return read_stats_active_boards(self.host, self.port, timeout=effective_timeout)

    def pools(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[dict]:
        """Query 'pools' endpoint returning primary pool dictionary."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return read_pools(self.host, self.port, timeout=effective_timeout)

    def version(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[dict]:
        """Query 'version' endpoint returning miner version dictionary."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return read_version(self.host, self.port, timeout=effective_timeout)


def query_cgminer(
    host: str,
    port: int = 4028,
    command: Union[str, bytes] = "summary",
    parameter: Optional[str] = None,
    timeout: float = 5.0,
) -> Optional[dict]:
    """
    Execute a raw TCP command to CGMiner API (default port 4028).
    
    Handles socket timeouts, null-byte termination, and malformed JSON cleanly.
    Returns parsed dictionary or None on any network or parsing error.
    """
    if isinstance(command, bytes):
        payload = command
    else:
        req: Dict[str, Any] = {"command": command}
        if parameter is not None:
            req["parameter"] = parameter
        payload = (json.dumps(req) + "\n").encode("utf-8")

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(payload)
            chunks: List[bytes] = []
            total_bytes = 0
            while True:
                try:
                    data = sock.recv(4096)
                except (socket.timeout, TimeoutError):
                    # If data was already received, parse what we have (some ASICs keep TCP connection open)
                    if chunks:
                        break
                    raise
                if not data:
                    break
                chunks.append(data)
                total_bytes += len(data)
                if total_bytes > 10 * 1024 * 1024:  # 10MB memory safety ceiling
                    break
    except Exception as exc:
        _log_warn(f"[WARN] No se pudo leer {host}:{port} ({exc})")
        return None

    raw = b"".join(chunks).replace(b"\x00", b"")
    if not raw:
        return None

    try:
        parsed = json.loads(raw.decode("utf-8", errors="ignore"))
        return parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        _log_warn(f"[WARN] Error parseando respuesta de {host}:{port} ({exc})")
        return None


def read_summary(
    host: str,
    port: int,
    timeout: float = 5.0,
    query_fn: Optional[Callable[..., Optional[dict]]] = None,
) -> Tuple[Optional[float], Optional[int], bool, Optional[dict]]:
    """
    Query 'summary' from miner via CGMiner 4028.
    
    Returns:
        (rate_ths, elapsed, responded, first_summary_entry)
    """
    payload = b'{"command":"summary"}\n'
    query = query_fn or query_cgminer
    resp = query(host, port, payload, timeout=timeout)
    if not resp:
        return None, None, False, None
    summary = resp.get("SUMMARY")
    if not summary:
        return None, None, False, None
    first = summary[0] if isinstance(summary, list) and summary else summary
    if not isinstance(first, dict):
        return None, None, False, None
    elapsed = None
    if "Elapsed" in first:
        try:
            elapsed = int(first["Elapsed"])
        except (TypeError, ValueError):
            elapsed = None
    # Priority: GHS 5s -> GHS av -> MHS 5s -> MHS av
    candidates = [
        ("GHS 5s", 1_000),
        ("GHS av", 1_000),
        ("MHS 5s", 1_000_000),
        ("MHS av", 1_000_000),
    ]
    rate_ths = None
    for key, divisor in candidates:
        if key in first:
            try:
                rate_ths = float(first[key]) / divisor
                break
            except (TypeError, ValueError):
                continue
    return rate_ths, elapsed, True, first


def count_active_boards(stats_entry: dict) -> Optional[int]:
    """
    Count the number of active hashboards from a 'stats' response entry.
    
    Supports both modern firmware lists ('chain_acn': [x, y, z]) and
    legacy per-chain scalar fields ('chain_acn0', 'chain0_asicnum', 'chain0_alive').
    """
    if "chain_acn" in stats_entry and isinstance(stats_entry["chain_acn"], list):
        return sum(1 for v in stats_entry["chain_acn"] if isinstance(v, (int, float)) and v > 0)

    count = 0
    found = False
    for i in range(0, 10):
        key_acn = f"chain_acn{i}"
        key_num = f"chain{i}_asicnum"
        key_alive = f"chain{i}_alive"
        key_status = f"chain{i}_status"
        if key_acn in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_acn, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_num in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_num, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_alive in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_alive, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_status in stats_entry:
            found = True
            if str(stats_entry.get(key_status, "")).lower() in ("alive", "o", "ok"):
                count += 1

    return count if found else None


def read_stats_snapshot(
    host: str,
    port: int,
    timeout: float = 5.0,
    query_fn: Optional[Callable[..., Optional[dict]]] = None,
) -> Tuple[Optional[int], bool, Optional[dict]]:
    """
    Query 'stats' from miner via CGMiner 4028.
    
    Returns:
        (active_boards, responded, full_response_dict)
    """
    payload = b'{"command":"stats"}\n'
    query = query_fn or query_cgminer
    resp = query(host, port, payload, timeout=timeout)
    if not resp:
        return None, False, None
    stats = resp.get("STATS")
    if not stats:
        return None, True, resp
    entries = stats if isinstance(stats, list) else [stats]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        active_boards = count_active_boards(entry)
        if active_boards is not None:
            return active_boards, True, resp
    return None, True, resp


def read_stats_active_boards(
    host: str,
    port: int,
    timeout: float = 5.0,
    query_fn: Optional[Callable[..., Optional[dict]]] = None,
) -> Tuple[Optional[int], bool]:
    """
    Convenience wrapper returning (active_boards, responded) from read_stats_snapshot.
    """
    active_boards, responded, _ = read_stats_snapshot(host, port, timeout=timeout, query_fn=query_fn)
    return active_boards, responded


def read_pools(
    host: str,
    port: int,
    timeout: float = 5.0,
    query_fn: Optional[Callable[..., Optional[dict]]] = None,
) -> Optional[dict]:
    """
    Query 'pools' from miner via CGMiner 4028.
    
    Returns primary pool dict or None.
    """
    payload = b'{"command":"pools"}\n'
    query = query_fn or query_cgminer
    resp = query(host, port, payload, timeout=timeout)
    if not resp:
        return None
    pools = resp.get("POOLS")
    if not pools:
        return None
    entry = pools[0] if isinstance(pools, list) and pools else pools
    return entry if isinstance(entry, dict) else None


def read_version(
    host: str,
    port: int,
    timeout: float = 5.0,
    query_fn: Optional[Callable[..., Optional[dict]]] = None,
) -> Optional[dict]:
    """
    Query 'version' from miner via CGMiner 4028.
    
    Returns version dict or None.
    """
    payload = b'{"command":"version"}\n'
    query = query_fn or query_cgminer
    resp = query(host, port, payload, timeout=timeout)
    if not resp:
        return None
    versions = resp.get("VERSION")
    if not versions:
        return None
    entry = versions[0] if isinstance(versions, list) and versions else versions
    return entry if isinstance(entry, dict) else None


def extract_temps(stats_entry: dict) -> list[float]:
    """
    Extract up to 3 positive temperatures from a stats entry, sorted ascending.
    """
    temps = []
    for key, val in stats_entry.items():
        if not str(key).lower().startswith("temp"):
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if fval > 0:
            temps.append(fval)
    temps = sorted(temps)[:3]
    return temps


def fw_hint(*texts: str) -> str:
    """
    Analyze banner/version strings to infer firmware type ('VNISH?', 'STOCK?', or 'N/A').
    """
    hay = " ".join(t for t in texts if t).lower()
    if not hay:
        return "N/A"
    if "vnish" in hay or "asic.to" in hay or "asicto" in hay:
        return "VNISH?"
    if "bitmain" in hay or "stock" in hay:
        return "STOCK?"
    return "N/A"


# Backwards compatibility aliases matching exact private symbol names
_read_command = query_cgminer
_count_active_boards = count_active_boards
_extract_temps = extract_temps
_fw_hint = fw_hint
