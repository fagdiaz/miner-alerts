"""Fast Phase Drop vs Connectivity Discriminator (Spec 051).

Provides high-speed heuristic classification of unison miner drops to distinguish
electrical circuit trips (elevator thermal-magnetic breaker or head line cut)
from local host network isolation (switch/router failure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import socket
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from app.telegram.help_center import visible_line_width, wrap_mobile_lines


class PhaseDropVerdict(str, Enum):
    """Classification of concurrent miner drop events."""
    NORMAL = "normal"
    NETWORK_ISOLATION = "network_isolation"
    PHASE_DROP_ELEVATOR = "phase_drop_elevator"
    PHASE_DROP_FLEET = "phase_drop_fleet"
    INDIVIDUAL_FAILURES = "individual_failures"


@dataclass
class PhaseDropAssessment:
    """Assessment summary of a phase drop evaluation."""
    verdict: PhaseDropVerdict
    affected_groups: List[str] = field(default_factory=list)
    failed_miners: List[str] = field(default_factory=list)
    responded_miners: List[str] = field(default_factory=list)
    active_groups: List[str] = field(default_factory=list)
    host_network_ok: bool = True
    details: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class PhaseDropConfig:
    """Configuration options for phase drop discriminator."""
    enabled: bool = True
    gateway_host: Optional[str] = None
    gateway_port: int = 53
    gateway_timeout_seconds: float = 0.5
    cooldown_seconds: float = 300.0


def parse_phase_drop_config(config: Dict[str, Any]) -> PhaseDropConfig:
    """Parses phase drop settings from config dict supporting both sub-dict and flat keys."""
    sub = config.get("phase_drop_discriminator", {})
    if not isinstance(sub, dict):
        sub = {}

    enabled = config.get("phase_drop_discriminator_enabled")
    if enabled is None:
        enabled = sub.get("enabled", True)

    gw_host = config.get("phase_drop_gateway_host") or sub.get("gateway_host") or None
    gw_port = config.get("phase_drop_gateway_port") or sub.get("gateway_port", 53)
    gw_timeout = config.get("phase_drop_gateway_timeout_seconds") or sub.get("gateway_timeout_seconds", 0.5)
    cooldown = config.get("phase_drop_cooldown_seconds") or sub.get("cooldown_seconds", 300.0)

    return PhaseDropConfig(
        enabled=bool(enabled),
        gateway_host=str(gw_host) if gw_host else None,
        gateway_port=int(gw_port),
        gateway_timeout_seconds=float(gw_timeout),
        cooldown_seconds=float(cooldown),
    )


def check_host_gateway_reachability(
    gateway_host: Optional[str] = None,
    port: int = 53,
    timeout: float = 0.3,
    socket_fn: Optional[Callable[..., Any]] = None,
) -> bool:
    """
    Checks if host local network/gateway is operational using a fast non-blocking socket test (<= 500ms).
    If gateway_host is provided, tests it first. Otherwise probes standard DNS endpoints.
    """
    targets = []
    if gateway_host and str(gateway_host).strip():
        targets.append((str(gateway_host).strip(), int(port)))
    else:
        # Standard DNS resolvers to verify outbound WAN/LAN gateway
        targets.append(("1.1.1.1", 53))
        targets.append(("8.8.8.8", 53))

    connector = socket_fn or socket.create_connection
    for host, p in targets:
        try:
            sock = connector((host, p), timeout=float(timeout))
            if hasattr(sock, "close"):
                sock.close()
            return True
        except Exception:
            continue
    return False


def _extract_miner_id(miner: Dict[str, Any] | str) -> str:
    """Extract standard unique identifier for miner."""
    if isinstance(miner, dict):
        return str(miner.get("name") or miner.get("host") or "")
    return str(miner)


def _extract_miner_name(miner: Dict[str, Any] | str) -> str:
    """Extract readable name for miner."""
    if isinstance(miner, dict):
        return str(miner.get("name") or miner.get("host") or "Minero")
    return str(miner)


def _extract_group(
    miner: Dict[str, Any] | str,
    elevator_groups: Optional[Dict[str, str]] = None,
) -> str:
    """Resolve electrical group for miner."""
    m_id = _extract_miner_id(miner)
    if elevator_groups and m_id in elevator_groups:
        return str(elevator_groups[m_id])
    if isinstance(miner, dict):
        return str(miner.get("electrical_group") or "default")
    return "default"


def evaluate_phase_drop(
    failed_miners: Sequence[Dict[str, Any] | str],
    responded_miners: Sequence[Dict[str, Any] | str],
    host_network_ok: bool,
    maintenance_miner_ids: Optional[Set[str] | Sequence[str]] = None,
    elevator_groups: Optional[Dict[str, str]] = None,
    min_group_size: int = 2,
) -> PhaseDropAssessment:
    """
    Correlates concurrent miner failures against electrical group topology.

    Rules:
    1. Miners in maintenance_miner_ids are excluded (shutdown maintenance / snooze).
    2. If no non-maintenance miners failed: NORMAL.
    3. If 100% of non-maintenance fleet failed simultaneously:
       - If not host_network_ok: NETWORK_ISOLATION (host cable/switch down; suppress alert).
       - If host_network_ok and fleet size >= min_group_size: PHASE_DROP_FLEET.
       - If host_network_ok and fleet size < min_group_size: INDIVIDUAL_FAILURES.
    4. If a subset of miners failed:
       - If 100% of miners in one or more electrical groups (each having >= min_group_size)
         failed in the same epoch, while at least one other group responded: PHASE_DROP_ELEVATOR.
       - Otherwise: INDIVIDUAL_FAILURES.
    """
    maint_set: Set[str] = set(maintenance_miner_ids or [])

    # Filter out miners currently undergoing intentional maintenance
    active_failed = [m for m in failed_miners if _extract_miner_id(m) not in maint_set]
    active_responded = [m for m in responded_miners if _extract_miner_id(m) not in maint_set]

    failed_names = [_extract_miner_name(m) for m in active_failed]
    responded_names = [_extract_miner_name(m) for m in active_responded]
    total_active = len(active_failed) + len(active_responded)

    if not active_failed:
        return PhaseDropAssessment(
            verdict=PhaseDropVerdict.NORMAL,
            affected_groups=[],
            failed_miners=[],
            responded_miners=responded_names,
            active_groups=[],
            host_network_ok=host_network_ok,
            details="Todos los mineros activos responden con normalidad.",
        )

    # Group miners by electrical group
    group_failed: Dict[str, List[Dict[str, Any] | str]] = {}
    group_responded: Dict[str, List[Dict[str, Any] | str]] = {}

    for m in active_failed:
        grp = _extract_group(m, elevator_groups)
        group_failed.setdefault(grp, []).append(m)

    for m in active_responded:
        grp = _extract_group(m, elevator_groups)
        group_responded.setdefault(grp, []).append(m)

    all_groups = set(group_failed.keys()) | set(group_responded.keys())

    # Case: Whole fleet dropped at once
    if len(active_responded) == 0:
        if not host_network_ok:
            return PhaseDropAssessment(
                verdict=PhaseDropVerdict.NETWORK_ISOLATION,
                affected_groups=sorted(list(all_groups)),
                failed_miners=failed_names,
                responded_miners=[],
                active_groups=[],
                host_network_ok=False,
                details=(
                    f"Host sin conectividad de red/gateway; "
                    f"{len(active_failed)} minero(s) inaccesibles. Falso positivo eléctrico suprimido."
                ),
            )
        if total_active >= min_group_size:
            return PhaseDropAssessment(
                verdict=PhaseDropVerdict.PHASE_DROP_FLEET,
                affected_groups=sorted(list(all_groups)),
                failed_miners=failed_names,
                responded_miners=[],
                active_groups=[],
                host_network_ok=True,
                details=(
                    f"Corte eléctrico general o disparo de cabecera: "
                    f"100% de la flota ({len(active_failed)} mineros) desconectada al unísono."
                ),
            )
        return PhaseDropAssessment(
            verdict=PhaseDropVerdict.INDIVIDUAL_FAILURES,
            affected_groups=sorted(list(all_groups)),
            failed_miners=failed_names,
            responded_miners=[],
            active_groups=[],
            host_network_ok=True,
            details=f"Fallo de {len(active_failed)} minero(s) sin quórum de grupo para corte de fase.",
        )

    # Case: Subset dropped. Check per-group unisons
    dropped_groups: List[str] = []
    surviving_groups: List[str] = []

    for grp in sorted(all_groups):
        failed_count = len(group_failed.get(grp, []))
        resp_count = len(group_responded.get(grp, []))
        total_grp = failed_count + resp_count

        if total_grp >= min_group_size and resp_count == 0 and failed_count > 0:
            dropped_groups.append(grp)
        elif resp_count > 0:
            surviving_groups.append(grp)

    if dropped_groups:
        return PhaseDropAssessment(
            verdict=PhaseDropVerdict.PHASE_DROP_ELEVATOR,
            affected_groups=dropped_groups,
            failed_miners=failed_names,
            responded_miners=responded_names,
            active_groups=surviving_groups,
            host_network_ok=host_network_ok,
            details=(
                f"Disparo de circuito en grupo(s) {dropped_groups}. "
                f"Grupo(s) activo(s): {surviving_groups}."
            ),
        )

    return PhaseDropAssessment(
        verdict=PhaseDropVerdict.INDIVIDUAL_FAILURES,
        affected_groups=sorted(list(group_failed.keys())),
        failed_miners=failed_names,
        responded_miners=responded_names,
        active_groups=sorted(list(group_responded.keys())),
        host_network_ok=host_network_ok,
        details=(
            f"Fallo individual de {len(active_failed)} minero(s); "
            f"no alcanza el 100% de ningún grupo eléctrico."
        ),
    )


def render_phase_drop_alert(assessment: PhaseDropAssessment) -> str:
    """
    Renders Telegram alert card for phase drop or network isolation events.
    Strictly guarantees visible_line_width <= 32 on 100% of lines (RFC C1-C10).
    """
    raw_lines: List[str] = []

    if assessment.verdict == PhaseDropVerdict.PHASE_DROP_ELEVATOR:
        raw_lines.append("⚡ *DISPARO DE CIRCUITO*")
        raw_lines.append("─" * 32)
        grps_str = ", ".join(assessment.affected_groups)
        raw_lines.extend(wrap_mobile_lines(f"Circuito: *{grps_str}*", width=32))
        raw_lines.append("Estado: 🛑 Desenergizado")
        raw_lines.append("─" * 32)
        raw_lines.append(f"Equipos caídos ({len(assessment.failed_miners)}):")
        for name in assessment.failed_miners:
            raw_lines.extend(wrap_mobile_lines(f"• *{name}*", width=32))
            raw_lines.append("  └ TCP: Sin respuesta")
        if assessment.active_groups:
            raw_lines.append("─" * 32)
            raw_lines.append("Circuitos activos:")
            for grp in assessment.active_groups:
                raw_lines.extend(wrap_mobile_lines(f"• *{grp}*: OK", width=32))
        raw_lines.append("─" * 32)
        raw_lines.append("⚠️ *ACCIÓN INMEDIATA*:")
        raw_lines.append("Verificar térmica/elevador")
        raw_lines.append("en tablero principal.")

    elif assessment.verdict == PhaseDropVerdict.PHASE_DROP_FLEET:
        raw_lines.append("⚡ *CORTE ELÉCTRICO GENERAL*")
        raw_lines.append("─" * 32)
        raw_lines.append("Estado: 🛑 Flota sin energía")
        raw_lines.append("Red host: 🌐 Conectado OK")
        raw_lines.append("─" * 32)
        raw_lines.append(f"Equipos caídos ({len(assessment.failed_miners)}):")
        for name in assessment.failed_miners:
            raw_lines.extend(wrap_mobile_lines(f"• *{name}*", width=32))
            raw_lines.append("  └ TCP: Sin respuesta")
        raw_lines.append("─" * 32)
        raw_lines.append("⚠️ *ACCIÓN INMEDIATA*:")
        raw_lines.append("Revisar térmica de cabecera")
        raw_lines.append("o corte de distribuidora.")

    elif assessment.verdict == PhaseDropVerdict.NETWORK_ISOLATION:
        raw_lines.append("🌐 *AISLAMIENTO DE RED HOST*")
        raw_lines.append("─" * 32)
        raw_lines.append("Host monitor sin red/gateway.")
        raw_lines.append("Alerta eléctrica suprimida.")
        raw_lines.append("─" * 32)
        raw_lines.append("⚠️ *ACCIÓN REQUERIDA*:")
        raw_lines.append("Verificar switch / router.")

    else:
        raw_lines.append("⚠️ *FALLO INDIVIDUAL MINEROS*")
        raw_lines.append("─" * 32)
        raw_lines.append("No coincide con corte de fase.")
        raw_lines.append(f"Equipos caídos: {len(assessment.failed_miners)}")

    # Double-check every line with visible_line_width and enforce <= 32
    final_lines: List[str] = []
    for line in raw_lines:
        if visible_line_width(line) <= 32:
            final_lines.append(line)
        else:
            final_lines.extend(wrap_mobile_lines(line, width=32))

    return "\n".join(final_lines)


def process_phase_drop_cycle(
    miners: Sequence[Dict[str, Any]],
    states: Dict[str, Any],
    tick_failed_miners: Sequence[Dict[str, Any]],
    tick_responded_miners: Sequence[Dict[str, Any]],
    maintenance_miner_ids: Set[str],
    phase_drop_config: PhaseDropConfig,
    last_alert_ts: Dict[str, float],
    active_phase_drops: Set[str],
    now_ts: float,
    fails_before_alert: int,
    send_telegram_fn: Optional[Callable[..., Any]] = None,
    record_event_fn: Optional[Callable[..., Any]] = None,
    log_fn: Optional[Callable[[str], None]] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    reachability_fn: Optional[Callable[..., bool]] = None,
) -> PhaseDropAssessment:
    """
    Executes one evaluation cycle of the Fast Phase Drop Discriminator.
    Bypasses normal 3-tick hysteresis when an electrical circuit drop is detected,
    records event in event_store, and dispatches high-priority Telegram alert.
    """
    if not phase_drop_config.enabled:
        return PhaseDropAssessment(
            verdict=PhaseDropVerdict.NORMAL,
            details="Discriminador de caída de fase desactivado por configuración.",
        )

    probe_fn = reachability_fn or check_host_gateway_reachability
    host_ok = probe_fn(
        gateway_host=phase_drop_config.gateway_host,
        port=phase_drop_config.gateway_port,
        timeout=phase_drop_config.gateway_timeout_seconds,
    )

    assessment = evaluate_phase_drop(
        failed_miners=tick_failed_miners,
        responded_miners=tick_responded_miners,
        host_network_ok=host_ok,
        maintenance_miner_ids=maintenance_miner_ids,
    )

    # If all recovered or normal, clear active phase drops
    if assessment.verdict == PhaseDropVerdict.NORMAL:
        if active_phase_drops:
            if log_fn:
                log_fn(f"[PHASE_DROP] Circuit recovery confirmed: active={list(active_phase_drops)}")
            active_phase_drops.clear()
        return assessment

    # If network isolation, log and suppress electrical alerts
    if assessment.verdict == PhaseDropVerdict.NETWORK_ISOLATION:
        if log_fn:
            log_fn(f"[PHASE_DROP] {assessment.details}")
        return assessment

    # If individual failures without unison, no bypass or phase drop alert
    if assessment.verdict == PhaseDropVerdict.INDIVIDUAL_FAILURES:
        return assessment

    # Verdict is PHASE_DROP_ELEVATOR or PHASE_DROP_FLEET:
    # 1. Hysteresis bypass: mark affected miners offline immediately
    affected_groups_set = set(assessment.affected_groups)
    for m in tick_failed_miners:
        grp = _extract_group(m)
        if grp in affected_groups_set or assessment.verdict == PhaseDropVerdict.PHASE_DROP_FLEET:
            sk = f"{m.get('name')}|{m.get('host')}:{m.get('port')}"
            st = states.get(sk)
            if st is not None:
                st.offline_streak = max(st.offline_streak, fails_before_alert)
                st.state = "OFFLINE"

    # 2. Check cooldowns
    alert_due = False
    if assessment.verdict == PhaseDropVerdict.PHASE_DROP_FLEET:
        last_ts = last_alert_ts.get("__fleet__", 0.0)
        if (now_ts - last_ts) >= phase_drop_config.cooldown_seconds:
            alert_due = True
            last_alert_ts["__fleet__"] = now_ts
            active_phase_drops.add("__fleet__")
    else:
        for grp in assessment.affected_groups:
            last_ts = last_alert_ts.get(grp, 0.0)
            if (now_ts - last_ts) >= phase_drop_config.cooldown_seconds:
                alert_due = True
                last_alert_ts[grp] = now_ts
                active_phase_drops.add(grp)

    # 3. Dispatch alert and record event
    if alert_due:
        card = render_phase_drop_alert(assessment)
        if log_fn:
            log_fn(
                f"[PHASE_DROP] Alerting verdict={assessment.verdict.value} "
                f"affected={assessment.affected_groups} failed={assessment.failed_miners}"
            )
        if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
            send_telegram_fn(
                bot_token,
                str(chat_id),
                card,
                "ERROR",
                f"phase_drop_{assessment.verdict.value}",
            )
        if record_event_fn:
            record_event_fn(
                occurred_ts=now_ts,
                miner_key=",".join(assessment.failed_miners),
                miner_name=f"Circuito {','.join(assessment.affected_groups)}",
                host="",
                event_type="electrical_phase_drop",
                severity="critical",
                previous_state="OK",
                new_state="OFFLINE",
                summary=f"Disparo de circuito detectado en {','.join(assessment.affected_groups)}",
                details={
                    "verdict": assessment.verdict.value,
                    "affected_groups": assessment.affected_groups,
                    "failed_miners": assessment.failed_miners,
                    "active_groups": assessment.active_groups,
                    "host_network_ok": assessment.host_network_ok,
                },
            )

    return assessment

