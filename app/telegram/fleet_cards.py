"""
fleet_cards.py — Mobile-First Diagnostic Cards & Fleet Reports (Spec 046).

Pure, deterministic renderers and keyboard builders for Telegram Mobile.
All data lines strictly adhere to visible_line_width <= 32 columns.
Zero I/O, zero database connections, zero threading locks.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from app.core.event_store import EventStore

STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"
STATE_HASHBOARD = "HASHBOARD"

from app.telegram.command_center import CC_NAV_MAIN, build_inline_keyboard
from app.telegram.help_center import (
    escape_markdown,
    strip_markdown,
    visible_line_width,
    wrap_mobile_lines,
)

# ── Protocol & Callback Constants ─────────────────────────────────────
DIAG_PREFIX = "diag:"
DIAG_REF_STATUS = "diag:ref:status"
DIAG_REF_FANS = "diag:ref:fans"
DIAG_REF_EFF = "diag:ref:eff"
DIAG_REF_PRESETS = "diag:ref:presets"
DIAG_REF_BALANCER = "diag:ref:balancer"
DIAG_REF_ELEV = "diag:ref:elev"
DIAG_REF_DIGEST = "diag:ref:digest"
DIAG_REF_EVENTS = "diag:ref:events"
DIAG_REF_CHAINS = "diag:ref:chains"

MOBILE_LINE_WIDTH_LIMIT = 32
MOBILE_CARD_SEPARATOR = "─" * 28

SUPPORTED_REPORT_TYPES = (
    "status",
    "fans",
    "eff",
    "presets",
    "balancer",
    "elev",
    "digest",
    "events",
    "chains",
    "anom_comp",
    "anom_desc",
    "anomalies",
)


# ── Callback Parser ───────────────────────────────────────────────────
@dataclass(frozen=True)
class DiagnosticCallbackAction:
    action: str  # e.g. "ref", "view"
    report_type: str  # e.g. "status", "fans", "eff", "presets", "balancer", "chains", etc.
    miner_id: Optional[str] = None


def parse_diagnostic_callback(callback_data: str) -> Optional[DiagnosticCallbackAction]:
    """Strictly parse and validate diagnostic callbacks (limit <= 64 bytes UTF-8)."""
    if not callback_data:
        return None
    if len(callback_data.encode("utf-8")) > 64:
        return None

    parts = callback_data.split(":")
    if len(parts) < 3 or parts[0] != "diag":
        return None

    action = parts[1]
    # Support direct miner view: diag:chains:<miner_id>
    if action == "chains" and len(parts) == 3:
        return DiagnosticCallbackAction(action="view", report_type="chains", miner_id=parts[2])

    if action != "ref":
        return None

    report_type = parts[2]
    if report_type not in SUPPORTED_REPORT_TYPES:
        return None

    miner_id = None
    if len(parts) == 4 and report_type == "chains":
        miner_id = parts[3]
    elif len(parts) != 3:
        return None

    return DiagnosticCallbackAction(action=action, report_type=report_type, miner_id=miner_id)


# ── Keyboard Builder ──────────────────────────────────────────────────
def build_anomalies_keyboard(current_view: str = "compact") -> Dict[str, Any]:
    """Generate inline keyboard for 24h anomalies report with interactive view toggle."""
    if current_view == "compact":
        toggle_btn = {"text": "🔍 Ver Detalle", "callback_data": "diag:ref:anom_desc"}
        refresh_cb = "diag:ref:anom_comp"
    else:
        toggle_btn = {"text": "📋 Ver 1 Fila", "callback_data": "diag:ref:anom_comp"}
        refresh_cb = "diag:ref:anom_desc"

    return build_inline_keyboard([
        [
            toggle_btn,
            {"text": "🔄 Actualizar", "callback_data": refresh_cb},
        ],
        [
            {"text": "☀️ Reporte Diario", "callback_data": "diag:ref:digest"},
            {"text": "📱 Menú", "callback_data": CC_NAV_MAIN},
        ],
    ])


def build_firmware_corruption_keyboard(miner_id: str) -> Dict[str, Any]:
    """Build interactive action keyboard for firmware configuration corruption alert (Spec 080)."""
    short_id = str(miner_id).replace("S19JPRO-", "").replace("s19jpro-", "").replace("S19-", "")
    return build_inline_keyboard([
        [
            {"text": "⚡ Solicitar Reinicio", "callback_data": f"cc:act:rb_req:{short_id}"},
            {"text": "🔍 Diagnóstico", "callback_data": "diag:ref:diagnose"},
        ],
        [
            {"text": "☀️ Reporte", "callback_data": "diag:ref:digest"},
            {"text": "📱 Menú", "callback_data": CC_NAV_MAIN},
        ],
    ])


def build_diagnostic_keyboard(report_type: str) -> Dict[str, Any]:
    """Generate inline keyboard for diagnostic reports with 1-tap refresh and return."""
    ref_cb = f"diag:ref:{report_type}"
    if report_type == "status":
        return build_inline_keyboard([
            [
                {"text": "🔄 Actualizar", "callback_data": ref_cb},
                {"text": "📊 Métricas", "callback_data": "cc:nav:metrics"},
                {"text": "📱 Menú", "callback_data": CC_NAV_MAIN},
            ]
        ])
    elif report_type == "digest":
        return build_inline_keyboard([
            [
                {"text": "🔄 Actualizar", "callback_data": ref_cb},
                {"text": "📱 Menú", "callback_data": CC_NAV_MAIN},
            ],
            [
                {"text": "📋 Anomalías (1 Fila)", "callback_data": "diag:ref:anom_comp"},
                {"text": "🔍 Anomalías (Detalle)", "callback_data": "diag:ref:anom_desc"},
            ],
        ])
    elif report_type in ("anom_comp", "anomalies"):
        return build_anomalies_keyboard("compact")
    elif report_type == "anom_desc":
        return build_anomalies_keyboard("detailed")

    return build_inline_keyboard([
        [
            {"text": "🔄 Actualizar", "callback_data": ref_cb},
            {"text": "📱 Menú", "callback_data": CC_NAV_MAIN},
        ]
    ])


def build_chains_keyboard(
    current_miner: Optional[str] = None,
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build navigation keyboard for chain health inspection (/chains)."""
    miners_list = miners or []
    miner_buttons = []
    for m in miners_list:
        raw_name = str(m.get("name") or "")
        short_id = raw_name.replace("S19JPRO-", "").replace("S19-", "")
        if not short_id:
            raw_host = str(m.get("host") or m.get("ip") or "")
            short_id = raw_host.split(".")[-1] if "." in raw_host else raw_host

        if not short_id:
            continue

        # If inspecting this specific miner, highlight or skip
        if current_miner and (current_miner == short_id or current_miner == raw_name or current_miner in raw_name):
            continue

        miner_buttons.append({
            "text": f"🔍 {short_id}",
            "callback_data": f"diag:chains:{short_id}",
        })

    rows: List[List[Dict[str, str]]] = []
    if miner_buttons:
        # Group in chunks of up to 4 per row
        chunk_size = 4
        for i in range(0, len(miner_buttons), chunk_size):
            rows.append(miner_buttons[i : i + chunk_size])

    action_row = []
    if current_miner:
        action_row.append({"text": "📋 Ver Flota", "callback_data": "diag:ref:chains"})
        action_row.append({"text": "🔄 Actualizar", "callback_data": f"diag:chains:{current_miner}"})
    else:
        action_row.append({"text": "🔄 Actualizar Flota", "callback_data": "diag:ref:chains"})

    rows.append(action_row)
    rows.append([{"text": "📱 Menú Principal", "callback_data": CC_NAV_MAIN}])
    return build_inline_keyboard(rows)



# ── State Helpers ─────────────────────────────────────────────────────
def _short_host(host: str) -> str:
    """Return the last octet or short host string (e.g. '192.168.100.23' -> '.23')."""
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) == 4 and parts[-1].isdigit():
        return f".{parts[-1]}"
    return host[:8]


def _miner_state_badge(state_obj: Any) -> str:
    """Derive Unicode semaphore badge from MinerState or state string."""
    if state_obj is not None and getattr(state_obj, "is_shutdown_maintenance", False):
        return "⏸️"
    st = getattr(state_obj, "state", state_obj)
    if isinstance(st, str):
        st_upper = st.upper()
        if "OK" in st_upper:
            return "🟢"
        if "LOW" in st_upper:
            return "🟡"
        if "HASHBOARD" in st_upper:
            return "🟠"
        if "OFFLINE" in st_upper or "DEAD" in st_upper or "FAIL" in st_upper:
            return "🔴"
    return "⚪"


# ── Fleet Status Card (/status) ───────────────────────────────────────
def render_fleet_status_card(
    states: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    miners: Optional[List[Dict[str, Any]]] = None,
    now_ts_str: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render the mobile-first fleet status card (/status).

    Every line is strictly <= 32 visible columns without markdown tags.
    Total character count is strictly < 2,000 characters.
    """
    miners_list = miners or (config.get("miners", []) if config else [])
    time_label = f" ({now_ts_str})" if now_ts_str else ""
    header = f"📊 *ESTADO DE FLOTA*{time_label}"
    if visible_line_width(header) > MOBILE_LINE_WIDTH_LIMIT:
        header = f"📊 *ESTADO DE FLOTA*"

    lines: List[str] = [
        header,
        MOBILE_CARD_SEPARATOR,
    ]

    if not states and not miners_list:
        lines.append("⚠️ Sin lecturas disponibles.")
        lines.append("Reintente en unos segundos.")
        lines.append(MOBILE_CARD_SEPARATOR)
        return "\n".join(lines), build_diagnostic_keyboard("status")

    total_hashrate = 0.0
    total_power = 0.0
    total_responded = 0

    # Match each miner with state
    matched_miners: List[Tuple[Dict[str, Any], Optional[Any]]] = []
    if miners_list:
        for m in miners_list:
            m_name = m.get("name", "")
            m_host = m.get("host") or m.get("ip", "")
            m_port = m.get("port", 4028)
            st = None
            if states:
                candidates = [
                    f"{m_name}|{m_host}:{m_port}",
                    str(m_name),
                    str(m_host),
                ]
                for c in candidates:
                    if c in states:
                        st = states[c]
                        break
                if not st:
                    for k, v in states.items():
                        if m_name and str(m_name) in k:
                            st = v
                            break
                        if m_host and str(m_host) in k:
                            st = v
                            break
            matched_miners.append((m, st))
    else:
        for k, v in states.items():
            matched_miners.append(({"name": k, "host": ""}, v))

    for idx, (m, st) in enumerate(matched_miners):
        if idx > 0:
            lines.append("")  # Empty line between cards

        m_name = m.get("name") or "Miner"
        m_host = m.get("host") or ""
        short_ip = _short_host(m_host)
        badge = _miner_state_badge(st)

        # Title line: 🟢 *S19JPRO-23* (`.23`)
        ip_label = f" (`{short_ip}`)" if short_ip else ""
        name_line = f"{badge} *{escape_markdown(m_name)}*{ip_label}"
        if visible_line_width(name_line) > MOBILE_LINE_WIDTH_LIMIT:
            name_line = f"{badge} *{escape_markdown(m_name)}*"
        lines.append(name_line)

        if not st:
            lines.append("  • Estado: SIN DATOS")
            continue

        # Extract values
        st_state = getattr(st, "state", "UNKNOWN")
        rate = getattr(st, "last_rate_ths", None)
        active_b = getattr(st, "last_active_boards", None)
        exp_b = getattr(st, "last_expected_boards", None) or 3
        temp = getattr(st, "last_max_chip_temp", None)
        if temp is None:
            temp = getattr(st, "governor_last_temp_c", None)
        pwm = getattr(st, "last_fan_duty_percent", None)
        if pwm is None:
            pwm = getattr(st, "governor_duty", None)
        power = getattr(st, "last_power_w", None)
        if power is None:
            power = getattr(st, "governor_last_power_w", None)
        efficiency = getattr(st, "last_efficiency_j_th", None)
        if efficiency is None and power is not None and rate is not None and rate > 0:
            efficiency = round(power / rate, 1)
        silent = getattr(st, "silent_mode_active", False)
        snooze_until = getattr(st, "snooze_until_ts", None)

        if rate is not None and rate > 0:
            total_hashrate += rate
            total_responded += 1
        if power is not None and power > 0:
            total_power += power

        # Line 1: Hashrate & Boards
        if getattr(st, "is_shutdown_maintenance", False):
            lines.append("  • Estado: ⏸️ DETENIDO")
        elif st_state == "OFFLINE":
            lines.append("  • Estado: OFFLINE (0.0 TH/s)")
        elif rate is not None:
            boards_str = f" ({active_b}/{exp_b})" if active_b is not None else ""
            lines.append(f"  • Hash: {rate:.1f} TH/s{boards_str}")
        else:
            lines.append(f"  • Estado: {st_state}")

        # Line 2: Temp & Fans
        temp_str = f"{temp:.1f}°C" if temp is not None else "N/A"
        pwm_str = f"{pwm:.0f}%" if pwm is not None else "N/A"
        lines.append(f"  • Temp: {temp_str} | Fans: {pwm_str}")

        # Line 3: Power & J/TH
        if power is not None and efficiency is not None:
            lines.append(f"  • Pwr: {power:,.0f}W ({efficiency:.1f} J/T)")
        elif power is not None:
            lines.append(f"  • Potencia: {power:,.0f} W")
        elif efficiency is not None:
            lines.append(f"  • Eficiencia: {efficiency:.1f} J/TH")

        # Optional Line 4: Silent or Snooze status
        if getattr(st, "is_shutdown_maintenance", False):
            lines.append("  • Modo: ⏸️ Parada Segura")
        elif silent:
            lines.append("  • Modo: 🔇 Silencio")
        elif snooze_until is not None:
            lines.append("  • Estado: 🔕 Silenciado")

    # Summary section
    lines.append(MOBILE_CARD_SEPARATOR)
    kw_str = f"{total_power / 1000.0:.1f} kW" if total_power > 0 else "0.0 kW"
    summary_line = f"⚡ Total: {total_hashrate:.1f} TH/s | {kw_str}"
    if visible_line_width(summary_line) > MOBILE_LINE_WIDTH_LIMIT:
        lines.append(f"⚡ Hash: {total_hashrate:.1f} TH/s")
        lines.append(f"⚡ Carga: {kw_str}")
    else:
        lines.append(summary_line)

    return "\n".join(lines), build_diagnostic_keyboard("status")


# ── Spec 089: Diagnostic Text Builders & Resolution Helpers ──────────────

def display_name(raw_name: str) -> str:
    """Return compact display identifier for miner name (e.g. S19JPRO-23 -> 23)."""
    if "-" in raw_name:
        return raw_name.split("-")[-1]
    return raw_name


def format_rate(rate: Optional[float]) -> str:
    """Format hashrate in TH/s."""
    if rate is None:
        return "N/A"
    return f"{rate:.1f} TH/s"


def _short_text(text: str, limit: int = 160) -> str:
    """Bound text to a limit, appending ellipsis if truncated."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: max(0, limit - 3)]}..."


def resolve_miner(input_name: str, miners: list) -> Optional[dict]:
    """Resolve miner dictionary from name, display name, or host/ip."""
    needle = input_name.strip().lower()
    for miner in miners:
        raw = str(miner.get("name", "")).lower()
        disp = display_name(miner.get("name", "")).lower()
        if needle == raw or needle == disp:
            return miner
    for miner in miners:
        host = str(miner.get("host") or miner.get("ip") or "").strip().lower()
        if host and (needle == host or needle == host.split(":")[-1]):
            return miner
    return None


def build_stability_health_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
    *,
    now_ts: float,
    window_hours: float = 168.0,
    min_samples: int = 12,
    stale_after_seconds: float = 900.0,
) -> str:
    """Render bounded historical health without contacting miners or running actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico historico temporalmente no disponible."
    from app.core.stability_profile import analyze_stability, render_stability_assessment
    selected_miners = miners
    token = str(miner_token or "").strip()
    if token and token.lower() != "all":
        selected = resolve_miner(token, miners)
        if not selected:
            return "Miner no encontrado."
        selected_miners = [selected]
    omitted_miners = max(0, len(selected_miners) - 10)
    selected_miners = selected_miners[:10]

    safe_hours = max(1.0, min(float(window_hours), 720.0))
    safe_min_samples = max(3, min(int(min_samples), 288))
    safe_stale = max(30.0, float(stale_after_seconds))
    since_ts = float(now_ts) - safe_hours * 3600.0
    sample_limit = min(2_500, max(288, safe_min_samples * 20))
    blocks = ["HEALTH (historial local)"]
    for miner in selected_miners:
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        samples = event_store.list_samples(
            miner_key=state_key,
            since_ts=since_ts,
            limit=sample_limit,
        )
        if event_store.last_error:
            return "Diagnostico historico temporalmente no disponible."
        assessment = analyze_stability(
            samples,
            now_ts=now_ts,
            stale_after_seconds=safe_stale,
            min_samples=safe_min_samples,
        )
        blocks.append(
            render_stability_assessment(
                display_name(str(miner["name"])),
                assessment,
            )
        )
    if omitted_miners:
        blocks.append(f"... {omitted_miners} mineros omitidos por limite de salida.")
    return "\n\n".join(blocks)


def build_mining_quality_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
    *,
    now_ts: Optional[float] = None,
    window_hours: float = 24.0,
    min_intervals: int = 3,
    reject_warning_percent: float = 1.0,
    stale_warning_percent: float = 1.0,
    hw_error_delta_warning: int = 50,
    no_share_warning_seconds: float = 900.0,
) -> str:
    """Render bounded mining quality from SQLite without miner IO or actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico de calidad temporalmente no disponible."
    from app.core.mining_quality import analyze_mining_quality, render_mining_quality
    selected_miners = miners
    token = str(miner_token or "").strip()
    if token and token.lower() != "all":
        selected = resolve_miner(token, miners)
        if not selected:
            return "Miner no encontrado."
        selected_miners = [selected]
    omitted_miners = max(0, len(selected_miners) - 10)
    selected_miners = selected_miners[:10]

    safe_now = time.time() if now_ts is None else float(now_ts)
    safe_hours = max(1.0, min(float(window_hours), 720.0))
    safe_min_intervals = max(1, min(int(min_intervals), 48))
    since_ts = safe_now - safe_hours * 3600.0
    blocks = ["QUALITY (historial local)"]
    for miner in selected_miners:
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        samples = event_store.list_samples(
            miner_key=state_key,
            since_ts=since_ts,
            limit=100,
        )
        if event_store.last_error:
            return "Diagnostico de calidad temporalmente no disponible."
        assessment = analyze_mining_quality(
            samples,
            min_intervals=safe_min_intervals,
            reject_warning_percent=reject_warning_percent,
            stale_warning_percent=stale_warning_percent,
            hw_error_delta_warning=hw_error_delta_warning,
            no_share_warning_seconds=no_share_warning_seconds,
        )
        blocks.append(
            render_mining_quality(
                display_name(str(miner["name"])),
                assessment,
            )
        )
    if omitted_miners:
        blocks.append(f"... {omitted_miners} mineros omitidos por limite de salida.")
    return "\n\n".join(blocks)


def build_firmware_events_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
) -> str:
    """Render bounded Vnish evidence from SQLite without miner IO or actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico de firmware temporalmente no disponible."
    from app.vnish.logs import render_firmware_events

    token = str(miner_token or "").strip()
    miner_key: Optional[str] = None
    title = "FIRMWARE EVENTS"
    severities: Optional[tuple[str, ...]] = ("warning", "critical")
    limit = 6
    if token and token.lower() != "all":
        miner = resolve_miner(token, miners)
        if not miner:
            return "Miner no encontrado."
        miner_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        title = f"FIRMWARE EVENTS - {display_name(str(miner['name']))}"
        severities = None
    elif token.lower() == "all":
        severities = None
        limit = 10

    rows = event_store.list_firmware_events(
        limit=limit,
        miner_key=miner_key,
        severities=severities,
    )
    if event_store.last_error:
        return "Diagnostico de firmware temporalmente no disponible."
    return render_firmware_events(rows, title=title, limit=limit)


def build_miner_diagnosis_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
    *,
    now_ts: Optional[float] = None,
    stale_after_seconds: float = 900.0,
    firmware_window_hours: float = 24.0,
    collector_stale_seconds: float = 3_600.0,
) -> str:
    """Correlate bounded persisted evidence without live miner IO or actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico operativo temporalmente no disponible."
    from app.core.mining_quality import analyze_mining_quality
    selected_miners = miners
    token = str(miner_token or "").strip()
    if token and token.lower() != "all":
        selected = resolve_miner(token, miners)
        if not selected:
            return "Miner no encontrado."
        selected_miners = [selected]
    omitted = max(0, len(selected_miners) - 10)
    selected_miners = selected_miners[:10]

    effective_now = time.time() if now_ts is None else float(now_ts)
    safe_stale = max(30.0, min(float(stale_after_seconds), 86_400.0))
    safe_firmware_window = max(1.0, min(float(firmware_window_hours), 720.0))
    safe_collector_stale = max(60.0, min(float(collector_stale_seconds), 86_400.0))
    firmware_since = effective_now - safe_firmware_window * 3_600.0
    collector_run = event_store.latest_collector_run()
    collector_text = "SIN EJECUCIONES"
    if collector_run:
        collector_age = max(
            0.0,
            effective_now - float(collector_run.get("completed_ts") or 0.0),
        )
        collector_status = str(collector_run.get("status") or "unknown").upper()
        if collector_age > safe_collector_stale:
            collector_status = f"STALE/{collector_status}"
        collector_text = f"{collector_status} age={int(collector_age)}s"

    blocks: list[str] = []
    for miner in selected_miners:
        miner_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        samples = event_store.list_samples(miner_key=miner_key, limit=24)
        events = event_store.list_events(miner_key=miner_key, limit=1)
        decision = event_store.latest_reboot_decision(miner_key=miner_key)
        firmware = event_store.list_firmware_events(
            miner_key=miner_key,
            source_since_ts=firmware_since,
            severities=("warning", "critical"),
            limit=3,
        )
        if event_store.last_error:
            return "Diagnostico operativo temporalmente no disponible."

        name = display_name(str(miner["name"]))
        status = "NO_DATA"
        signal = "sin muestras persistidas"
        quality_label = "N/A"
        conclusion = "Esperar una muestra valida antes de diagnosticar."
        if samples:
            latest = samples[0]
            observed_ts = float(latest.get("observed_ts") or 0.0)
            age = max(0.0, effective_now - observed_ts)
            state = str(latest.get("state") or "UNKNOWN").upper()
            responded = bool(latest.get("responded"))
            rate = latest.get("rate_ths")
            threshold = latest.get("threshold_ths")
            signal = (
                f"{state} rate={format_rate(rate)} threshold={format_rate(threshold)} "
                f"age={int(age)}s"
            )
            quality = analyze_mining_quality(samples, min_intervals=3)
            quality_label = quality.status.upper()
            if age > safe_stale:
                status = "STALE"
                conclusion = "Telemetria vencida; no inferir necesidad de reboot."
            elif not responded or state in (STATE_OFFLINE, STATE_HASHBOARD):
                status = "CRITICAL"
                conclusion = "Falla actual verificable; revisar evidencia antes de actuar."
            elif state == STATE_LOW:
                status = "WATCH"
                conclusion = "Hashrate bajo actual; respetar sustained LOW y guardrails."
            elif firmware or quality.status in ("watch", "critical"):
                status = "WATCH"
                conclusion = "Senal actual estable con evidencia reciente para revisar."
            else:
                status = "OK"
                conclusion = "Sin evidencia operativa reciente que justifique intervenir."

        firmware_text = "sin warning/critical en ventana"
        if firmware:
            latest_firmware = firmware[0]
            firmware_text = (
                f"{len(firmware)} fresh; {latest_firmware.get('severity')} "
                f"{latest_firmware.get('code')} @ {latest_firmware.get('source_ts_text')}"
            )
        event_text = "sin evento"
        if events:
            latest_event = events[0]
            event_text = (
                f"{latest_event.get('event_type')} - "
                f"{_short_text(str(latest_event.get('summary') or ''), 80)}"
            )
        decision_text = str(decision.get("result")) if decision else "sin decision"
        blocks.append(
            "\n".join(
                [
                    f"DIAGNOSE {name} - {status}",
                    f"Signal: {signal}",
                    f"Quality: {quality_label}",
                    f"Firmware {safe_firmware_window:g}h: {firmware_text}",
                    f"Evento: {event_text}",
                    f"Auto-reboot: {decision_text}",
                    f"Collector: {collector_text}",
                    f"Conclusion: {conclusion}",
                ]
            )
        )
    if omitted:
        blocks.append(f"... {omitted} mineros omitidos por limite de salida.")
    return "\n\n".join(blocks)
