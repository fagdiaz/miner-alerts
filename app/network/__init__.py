from __future__ import annotations

from app.network.cgminer_client import (
    CGMinerClient,
    count_active_boards,
    extract_temps,
    fw_hint,
    query_cgminer,
    read_pools,
    read_stats_active_boards,
    read_stats_snapshot,
    read_summary,
    read_version,
)
from app.network.hashcore_client import (
    HashcoreClient,
    get_hashcore_cli_path,
    qa_verbose_enabled,
    run_hashcore_cli,
    run_hashcore_discovery,
)
from app.network.vnish_client import (
    DEFAULT_HTTP_TIMEOUT,
    VnishClient,
    get_cooling_settings,
    get_miner_status,
    get_overclock_settings,
    lock_miner,
    mask_secret,
    parse_miner_status_flags,
    restart_mining,
    safe_get_overclock_settings,
    safe_restart_mining,
    safe_set_fan_duty,
    safe_set_miner_preset,
    set_fan_duty,
    set_miner_preset,
    unlock_miner,
)

from app.network.gateway_heartbeat import GatewayHeartbeatWorker

__all__ = [
    # CGMiner 4028
    "CGMinerClient",
    "query_cgminer",
    "read_summary",
    "read_stats_snapshot",
    "read_stats_active_boards",
    "read_pools",
    "read_version",
    "count_active_boards",
    "extract_temps",
    "fw_hint",
    # Hashcore CLI
    "HashcoreClient",
    "get_hashcore_cli_path",
    "run_hashcore_discovery",
    "run_hashcore_cli",
    "qa_verbose_enabled",
    # Vnish REST
    "VnishClient",
    "DEFAULT_HTTP_TIMEOUT",
    "mask_secret",
    "unlock_miner",
    "lock_miner",
    "get_cooling_settings",
    "set_fan_duty",
    "safe_set_fan_duty",
    "restart_mining",
    "safe_restart_mining",
    "get_miner_status",
    "parse_miner_status_flags",
    "get_overclock_settings",
    "safe_get_overclock_settings",
    "set_miner_preset",
    "safe_set_miner_preset",
    # Spec 067: Gateway Heartbeat
    "GatewayHeartbeatWorker",
]
