"""Domain Data Models (Spec 091).

Defines core in-memory state representations for monitored ASIC miners,
including streak tracking, governance caches, and runtime metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.reboot_safety import STATE_OK


@dataclass
class MinerState:
    """Per-miner in-memory and persistent operational state container."""

    low_streak: int = 0
    offline_streak: int = 0
    ok_streak: int = 0
    state: str = STATE_OK
    initialized: bool = False
    last_elapsed: Optional[int] = None
    last_seen_ts: float = 0.0
    reboot_pending_until: float = 0.0
    reboot_pending_reason: str = ""
    reboot_pending_elapsed: Optional[int] = None
    last_reboot_ts: float = 0.0
    low_since_ts: Optional[float] = None
    hashboard_since_ts: Optional[float] = None
    last_auto_restart_ts: Optional[float] = None  # Spec 056: Soft mining restart timestamp
    auto_restart_count: int = 0                   # Spec 056: Soft mining restart attempts
    last_manual_reboot_ts: Optional[float] = None
    last_auto_reboot_ts: Optional[float] = None
    last_preset_change_ts: Optional[float] = None  # Timestamp del último preset/restart enviado por el monitor
    auto_reboot_timestamps: list = field(default_factory=list)
    degraded_mode: bool = False
    last_hourly_status_ts: Optional[float] = None
    snooze_until_ts: Optional[float] = None
    cooling_streak: int = 0
    last_cooling_warning_ts: Optional[float] = None
    efficiency_streak: int = 0
    last_efficiency_warning_ts: Optional[float] = None
    baseline_frequency_mhz: Optional[float] = None
    last_preset_warning_ts: Optional[float] = None
    # Spec 069: Deep Chain Telemetry & Predictive Chain Break Diagnostics (PROP-008)
    chain_warnings_ts: Dict[str, float] = field(default_factory=dict)
    # Spec 039: Fan Governor per-miner persistent state
    governor_duty: Optional[int] = None          # Last commanded duty %
    governor_holds: int = 0                       # Consecutive HOLD ticks
    governor_last_change_ts: float = 0.0          # Timestamp of last duty change
    governor_failures: int = 0                    # Consecutive HTTP failures
    governor_last_action: str = ""                # Last action string for /gov display
    governor_last_temp_c: Optional[float] = None  # Last temp seen by governor
    governor_last_power_w: Optional[float] = None # Last power (W) seen by governor
    governor_recovery_since_ts: Optional[float] = None # Timestamp when RECOVERY_MAX_COOLING started
    # Spec 040: Dynamic Preset Balancer per-miner persistent state
    balancer_preset: Optional[str] = None          # Last known or applied preset (e.g. "2700W")
    balancer_last_change_ts: float = 0.0          # Timestamp of last preset adjustment
    balancer_last_action: str = ""                # Last decision action string
    balancer_last_reason: str = ""                # Last decision reason
    # Spec 062: HW Error Tripwire & Anti-Cascade Lock
    hw_error_lock_until_ts: Optional[float] = None
    hw_error_locked_preset: Optional[str] = None
    # Dynamic Vnish Overclock & Autoswitch State Discovery
    vnish_discovered_target_power_w: Optional[float] = None
    vnish_discovered_preset: Optional[str] = None
    vnish_discovered_top_preset: Optional[str] = None
    vnish_discovered_switcher_enabled: Optional[bool] = None
    vnish_discovered_ts: float = 0.0
    # Spec 044: Silent Mode / Visitor Mode — hardware FSM, SEPARATE from snooze_until_ts
    silent_mode_active: bool = False
    silent_mode_revert_ts: Optional[float] = None      # Unix ts when mode expires; None = indefinite
    silent_mode_prev_duty: Optional[int] = None        # Hardware duty before silent mode activation
    silent_mode_prev_preset: Optional[str] = None      # VNish preset name before activation
    silent_mode_target_max_duty: int = 50              # Acoustic ceiling (default 50%)
    # Spec 048: Safe Fleet Shutdown & Maintenance Mode
    is_shutdown_maintenance: bool = False
    shutdown_maintenance_ts: float = 0.0
    # Spec 046: Live Telemetry Snapshot for /status & mobile fleet cards
    last_rate_ths: Optional[float] = None
    last_active_boards: Optional[int] = None
    last_expected_boards: Optional[int] = None
    last_max_chip_temp: Optional[float] = None
    last_fan_duty_percent: Optional[float] = None
    last_power_w: Optional[float] = None
    last_efficiency_j_th: Optional[float] = None
    last_responded: bool = False
    # Spec 063: Ambient-Aware Thermal PID (GOV-02)
    inlet_temp_c: Optional[float] = None
    # Spec 057: Intervention Governance & Vnish Libre Mode
    intervention_gov: Optional[Any] = None
    # Spec 075: Soft-Landing Recovery & APW12 Latch-Off Defense
    stopped_since_ts: Optional[float] = None
    is_pre_clamped: bool = False
    original_preset_before_clamp: Optional[str] = None
    staged_ramp_up_pending: bool = False
    staged_ramp_up_soak_start_ts: Optional[float] = None
    stock_firmware_fallback_notified: bool = False
    # P0 Thermal Tripwire Hardware Protection (Emergency Shedding & Pause)
    last_thermal_downstep_ts: float = 0.0
    last_thermal_pause_ts: float = 0.0
    thermal_pause_until_ts: Optional[float] = None
    thermal_lockout_until_ts: Optional[float] = None
    # Spec 081: Pending Preset Restart Watchdog (PROP-017)
    vnish_restart_required: bool = False
    vnish_restart_detected_ts: Optional[float] = None
    last_preset_restart_ts: Optional[float] = None
