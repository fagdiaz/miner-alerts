from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

ACTION_HOLD_STABLE = "HOLD_STABLE"
ACTION_STEP_DOWN_RESTARTS = "STEP_DOWN_RESTARTS"
ACTION_STEP_DOWN_CASCADE = "STEP_DOWN_CASCADE"
ACTION_STEP_UP_OPTIMIZE = "STEP_UP_OPTIMIZE"
ACTION_LOCKED_MAX = "LOCKED_MAX"
ACTION_LOCKED_MIN = "LOCKED_MIN"
ACTION_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PresetTier:
    name: str
    nominal_power_w: int
    nominal_ths: float
    order: int


# Standard Vnish overclock ladder for Antminer S19j Pro
DEFAULT_PRESET_LADDER: Tuple[PresetTier, ...] = (
    PresetTier(name="1600W", nominal_power_w=1600, nominal_ths=68.0, order=0),
    PresetTier(name="1740W", nominal_power_w=1740, nominal_ths=72.0, order=1),
    PresetTier(name="1900W", nominal_power_w=1900, nominal_ths=78.0, order=2),
    PresetTier(name="2100W", nominal_power_w=2100, nominal_ths=83.0, order=3),
    PresetTier(name="2300W", nominal_power_w=2300, nominal_ths=88.0, order=4),
    PresetTier(name="2500W", nominal_power_w=2500, nominal_ths=93.0, order=5),
    PresetTier(name="2700W", nominal_power_w=2700, nominal_ths=98.0, order=6),
    PresetTier(name="2800W", nominal_power_w=2800, nominal_ths=102.0, order=7),
)


@dataclass(frozen=True)
class StabilityMetrics:
    miner_name: str
    electrical_group: str              # e.g. "elevator_1", "elevator_2", "default"
    current_preset: str                # e.g. "2700W"
    restarts_24h: int                  # Restarts in last 24 hours
    restarts_72h: int                  # Restarts in last 72 hours
    hours_since_last_restart: float    # Continuous uptime hours without restart
    avg_hashrate_24h_ths: float        # Observed 24h average hashrate
    downtime_minutes_24h: float        # Total downtime minutes in 24h
    thermal_headroom_c: float          # Distance to 85.0°C thermal limit
    last_restart_epoch_s: float = 0.0  # Timestamp of most recent restart


@dataclass(frozen=True)
class BalancerConfig:
    enabled: bool = False
    dry_run: bool = True
    restarts_threshold_step_down: int = 2     # >= 2 restarts in 24h forces step down
    soak_hours_step_up: float = 72.0          # 72 hours without restarts to consider step up
    group_cascade_threshold: int = 2          # 2 miners restarting in group window triggers cascade step down
    group_cascade_window_s: float = 1800.0    # 30-minute cascade correlation window
    min_thermal_headroom_c: float = 4.0       # Minimum headroom below 85°C to allow step up
    default_max_preset: str = "2700W"         # Global default ceiling
    reboot_penalty_ths: float = 2.0           # Penalty per reboot in cost/benefit model


@dataclass(frozen=True)
class BalancerDecision:
    action: str
    miner_name: str
    electrical_group: str
    current_preset: str
    target_preset: str
    reason: str
    requires_write: bool
    estimated_effective_hashrate: float = 0.0


def compute_effective_hashrate(
    nominal_ths: float,
    restarts_count: int,
    reboot_penalty_ths: float = 2.0,
    avg_reboot_downtime_min: float = 10.0,
    window_hours: float = 24.0,
) -> float:
    """
    Calculate Net Effective Hashrate:
    H_eff = H_nominal * (1 - (N_restarts * T_downtime) / (window_hours * 60)) - (N_restarts * penalty)
    """
    total_minutes = max(1.0, window_hours * 60.0)
    downtime_ratio = min(1.0, (restarts_count * avg_reboot_downtime_min) / total_minutes)
    effective = (nominal_ths * (1.0 - downtime_ratio)) - (restarts_count * reboot_penalty_ths)
    return max(0.0, round(effective, 2))


def find_preset_index(preset_name: str, ladder: Optional[List[PresetTier]] = None) -> int:
    """Find index in ladder by name. Returns -1 if not found."""
    tiers = ladder or list(DEFAULT_PRESET_LADDER)
    clean = str(preset_name).strip().upper()
    for idx, tier in enumerate(tiers):
        if tier.name.upper() == clean or tier.name.upper() in clean:
            return idx
    return -1


def evaluate_balancer_step(
    metrics: StabilityMetrics,
    config: Optional[BalancerConfig] = None,
    ladder: Optional[List[PresetTier]] = None,
    group_metrics: Optional[List[StabilityMetrics]] = None,
    max_preset_override: Optional[str] = None,
) -> BalancerDecision:
    """
    Pure mathematical decision engine for Dynamic Power & Preset Balancer.
    Calculates whether to step down, step up, or hold current preset based on
    voltage sensitivity, restart frequency, and thermal headroom.
    Zero side-effects, zero I/O, 100% testable.
    """
    cfg = config or BalancerConfig()
    tiers = ladder or list(DEFAULT_PRESET_LADDER)
    curr_idx = find_preset_index(metrics.current_preset, tiers)

    if curr_idx < 0:
        return BalancerDecision(
            action=ACTION_UNKNOWN,
            miner_name=metrics.miner_name,
            electrical_group=metrics.electrical_group,
            current_preset=metrics.current_preset,
            target_preset=metrics.current_preset,
            reason=f"Preset actual '{metrics.current_preset}' desconocido en la escalera",
            requires_write=False,
            estimated_effective_hashrate=metrics.avg_hashrate_24h_ths,
        )

    current_tier = tiers[curr_idx]
    ceiling_name = max_preset_override or cfg.default_max_preset
    ceiling_idx = find_preset_index(ceiling_name, tiers)
    if ceiling_idx < 0:
        ceiling_idx = len(tiers) - 1

    eff_current = compute_effective_hashrate(
        nominal_ths=current_tier.nominal_ths,
        restarts_count=metrics.restarts_24h,
        reboot_penalty_ths=cfg.reboot_penalty_ths,
    )

    # 1. Check Group Cascade Condition
    # If other miners in the same electrical group had restarts recently,
    # the entire group steps down to relieve the sensitive voltage elevator.
    if group_metrics and metrics.electrical_group != "default":
        recent_peer_restarts = 0
        for peer in group_metrics:
            if peer.miner_name != metrics.miner_name and peer.electrical_group == metrics.electrical_group:
                if peer.restarts_24h >= 1 and peer.hours_since_last_restart < (cfg.group_cascade_window_s / 3600.0):
                    recent_peer_restarts += 1

        if recent_peer_restarts >= 1 and metrics.restarts_24h >= 1:
            if curr_idx > 0:
                target_tier = tiers[curr_idx - 1]
                return BalancerDecision(
                    action=ACTION_STEP_DOWN_CASCADE,
                    miner_name=metrics.miner_name,
                    electrical_group=metrics.electrical_group,
                    current_preset=current_tier.name,
                    target_preset=target_tier.name,
                    reason=f"Caída en cascada en elevador '{metrics.electrical_group}': {recent_peer_restarts} par(es) caídos",
                    requires_write=True,
                    estimated_effective_hashrate=eff_current,
                )

    # 2. Individual Step-Down: restarts in last 24h exceed threshold
    if metrics.restarts_24h >= cfg.restarts_threshold_step_down:
        if curr_idx > 0:
            target_tier = tiers[curr_idx - 1]
            return BalancerDecision(
                action=ACTION_STEP_DOWN_RESTARTS,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=target_tier.name,
                reason=f"Inestabilidad eléctrica ({metrics.restarts_24h} reinicios en 24h >= {cfg.restarts_threshold_step_down}): desescalando a {target_tier.name}",
                requires_write=True,
                estimated_effective_hashrate=eff_current,
            )
        else:
            return BalancerDecision(
                action=ACTION_LOCKED_MIN,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=current_tier.name,
                reason=f"Ya en preset mínimo ({current_tier.name}) pese a {metrics.restarts_24h} reinicios",
                requires_write=False,
                estimated_effective_hashrate=eff_current,
            )

    # 3. Individual Step-Up: long soak stability, zero restarts, comfortable thermal headroom
    if (
        metrics.hours_since_last_restart >= cfg.soak_hours_step_up
        and metrics.restarts_72h == 0
        and metrics.thermal_headroom_c >= cfg.min_thermal_headroom_c
    ):
        if curr_idx < ceiling_idx and curr_idx < len(tiers) - 1:
            target_tier = tiers[curr_idx + 1]
            return BalancerDecision(
                action=ACTION_STEP_UP_OPTIMIZE,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=target_tier.name,
                reason=f"Estabilidad comprobada ({metrics.hours_since_last_restart:.0f}h sin reinicios, margen {metrics.thermal_headroom_c:.1f}°C): subiendo a {target_tier.name}",
                requires_write=True,
                estimated_effective_hashrate=eff_current,
            )
        else:
            return BalancerDecision(
                action=ACTION_LOCKED_MAX,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=current_tier.name,
                reason=f"Alcanzado techo máximo configurado ({tiers[ceiling_idx].name}) con alta estabilidad",
                requires_write=False,
                estimated_effective_hashrate=eff_current,
            )

    # 4. Hold Stable: currently in balance
    return BalancerDecision(
        action=ACTION_HOLD_STABLE,
        miner_name=metrics.miner_name,
        electrical_group=metrics.electrical_group,
        current_preset=current_tier.name,
        target_preset=current_tier.name,
        reason=f"Operación estable en {current_tier.name} ({metrics.hours_since_last_restart:.0f}h uptime, {metrics.restarts_24h} reinicios 24h)",
        requires_write=False,
        estimated_effective_hashrate=eff_current,
    )


def infer_preset_name_from_power(
    power_w: Optional[float],
    ladder: Optional[List[PresetTier]] = None,
    default: str = "2500W",
) -> str:
    """Infer closest preset tier name from raw chain power in Watts."""
    if power_w is None or power_w <= 0:
        return default
    tiers = ladder or list(DEFAULT_PRESET_LADDER)
    best_tier = min(tiers, key=lambda t: abs(t.nominal_power_w - power_w))
    return best_tier.name


def extract_miner_stability_metrics(
    db_path: Path | str,
    miners: list,
    states: Optional[dict] = None,
    config: Optional[dict] = None,
    now_ts: Optional[float] = None,
) -> List[StabilityMetrics]:
    """Extract 24h/72h restart frequency and thermal metrics from SQLite."""
    now = now_ts or time.time()
    db_file = Path(db_path)
    if not db_file.exists():
        candidate = Path(__file__).resolve().parent.parent / db_path
        if candidate.exists():
            db_file = candidate
    metrics_list: List[StabilityMetrics] = []

    db_samples: Dict[str, dict] = {}
    restarts_by_miner: Dict[str, dict] = {}

    if db_file.exists():
        uri = f"file:{db_file.resolve().as_posix()}?mode=ro"
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            ts_24h = now - 86400.0
            ts_72h = now - 259200.0

            cursor.execute(
                """
                SELECT miner_key, miner_name, host, occurred_ts
                FROM operational_events
                WHERE event_type IN ('restart_detected', 'auto_reboot_success', 'manual_reboot_success')
                  AND occurred_ts >= ?
                ORDER BY occurred_ts DESC
                """,
                (ts_72h,),
            )
            for row in cursor.fetchall():
                m_key = str(row["miner_key"] or "")
                m_name = str(row["miner_name"] or "")
                m_host = str(row["host"] or "")
                occ_ts = float(row["occurred_ts"])

                for ident in (m_key, m_name, m_host):
                    if not ident:
                        continue
                    if ident not in restarts_by_miner:
                        restarts_by_miner[ident] = {"24h": 0, "72h": 0, "latest_ts": 0.0}
                    restarts_by_miner[ident]["72h"] += 1
                    if occ_ts >= ts_24h:
                        restarts_by_miner[ident]["24h"] += 1
                    if occ_ts > restarts_by_miner[ident]["latest_ts"]:
                        restarts_by_miner[ident]["latest_ts"] = occ_ts

            for miner in miners:
                m_name = miner.get("name")
                m_host = miner.get("host") or miner.get("ip")
                m_port = miner.get("port", 4028)
                candidate_keys = []
                if m_name and m_host:
                    candidate_keys.append(f"{m_name}|{m_host}:{m_port}")
                if m_host:
                    candidate_keys.append(str(m_host))
                if m_name:
                    candidate_keys.append(str(m_name))

                placeholders = ",".join("?" for _ in candidate_keys)
                cursor.execute(
                    f"""
                    SELECT rate_ths, max_temp_c, chain_power_w_total, elapsed_seconds
                    FROM telemetry_samples
                    WHERE miner_key IN ({placeholders}) OR miner_name = ? OR host = ?
                    ORDER BY observed_ts DESC
                    LIMIT 1
                    """,
                    (*candidate_keys, str(m_name or ""), str(m_host or "")),
                )
                sample_row = cursor.fetchone()
                if sample_row:
                    db_samples[str(m_name or m_host)] = dict(sample_row)

        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    for miner in miners:
        m_name = miner.get("name") or str(miner.get("host") or "unknown")
        m_host = miner.get("host") or miner.get("ip") or ""
        m_group = miner.get("electrical_group") or "default"

        r_info = {"24h": 0, "72h": 0, "latest_ts": 0.0}
        for k in (m_name, m_host, f"{m_name}|{m_host}:4028"):
            if k in restarts_by_miner:
                r_info = restarts_by_miner[k]
                break

        sample = db_samples.get(m_name) or db_samples.get(m_host) or {}
        max_temp = sample.get("max_temp_c")
        rate = float(sample.get("rate_ths") or 0.0)
        power = sample.get("chain_power_w_total")
        elapsed = sample.get("elapsed_seconds")

        headroom = max(0.0, 85.0 - max_temp) if max_temp is not None else 10.0

        if elapsed is not None and elapsed > 0:
            uptime_h = round(elapsed / 3600.0, 1)
        elif r_info["latest_ts"] > 0:
            uptime_h = round(max(0.0, now - r_info["latest_ts"]) / 3600.0, 1)
        else:
            uptime_h = 72.0

        preset_candidate = miner.get("preset")
        if not preset_candidate and states:
            for sk, st in states.items():
                if m_name in sk or (m_host and m_host in sk):
                    preset_candidate = getattr(st, "balancer_preset", None)
                    break
        if not preset_candidate:
            preset_candidate = infer_preset_name_from_power(power)

        metrics_list.append(
            StabilityMetrics(
                miner_name=m_name,
                electrical_group=m_group,
                current_preset=preset_candidate,
                restarts_24h=r_info["24h"],
                restarts_72h=r_info["72h"],
                hours_since_last_restart=uptime_h,
                avg_hashrate_24h_ths=rate,
                downtime_minutes_24h=r_info["24h"] * 10.0,
                thermal_headroom_c=round(headroom, 1),
                last_restart_epoch_s=r_info["latest_ts"],
            )
        )

    return metrics_list


def build_balancer_table_text(
    decisions: List[Tuple[StabilityMetrics, BalancerDecision]],
    is_enabled: bool = False,
    is_dry_run: bool = True,
) -> str:
    """Format fleet preset balance table grouped by electrical elevator."""
    status_icon = "🟢 ON" if is_enabled else "🔴 OFF"
    mode_icon = "🔇 DRY-RUN" if is_dry_run else "⚡ ACTIVO"
    lines = [
        f"⚖️ Balanceador de Presets y Elevadores — {status_icon} | {mode_icon}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not decisions:
        lines.append("No hay datos de mineros disponibles.")
        return "\n".join(lines)

    groups: Dict[str, List[Tuple[StabilityMetrics, BalancerDecision]]] = {}
    for m, d in decisions:
        groups.setdefault(m.electrical_group, []).append((m, d))

    for grp_name, items in groups.items():
        grp_title = f"🔌 Elevador / Grupo: {grp_name.upper()}"
        lines.append(grp_title)
        for m, d in items:
            action_icon = "🟢" if d.action == ACTION_HOLD_STABLE else ("⬆️" if d.action == ACTION_STEP_UP_OPTIMIZE else "⚠️")
            target_str = f" ➔ {d.target_preset}" if d.requires_write else ""
            lines.append(
                f"• {m.miner_name}: {m.current_preset}{target_str} | "
                f"R: {m.restarts_24h} (24h) / {m.restarts_72h} (72h) | Uptime: {m.hours_since_last_restart:.0f}h"
            )
            lines.append(f"  {action_icon} [{d.action}] {d.reason}")
        lines.append("────────────────────────────")

    lines.append("💡 Comandos: `/balancer on` | `/balancer off` | `/balancer setmax <minero> <preset>`")
    return "\n".join(lines)


def build_miner_balancer_detail_text(metrics: StabilityMetrics, decision: BalancerDecision) -> str:
    """Format individual miner balancer diagnostic card."""
    target_str = f" ➔ {decision.target_preset}" if decision.requires_write else ""
    return "\n".join([
        f"⚖️ Balanceador de Potencia — {metrics.miner_name}",
        f"• Elevador / Grupo: {metrics.electrical_group}",
        f"• Preset Actual: {metrics.current_preset}{target_str}",
        f"• Reinicios en 24h: {metrics.restarts_24h}",
        f"• Reinicios en 72h: {metrics.restarts_72h}",
        f"• Tiempo Continuo Uptime: {metrics.hours_since_last_restart:.1f} horas",
        f"• Margen Térmico Libre: {metrics.thermal_headroom_c:.1f}°C",
        f"• Hashrate Estimado Efectivo: {decision.estimated_effective_hashrate:.1f} TH/s",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💡 Diagnóstico: {decision.reason}",
    ])

