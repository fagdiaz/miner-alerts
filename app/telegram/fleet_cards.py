"""
fleet_cards.py — Mobile-First Diagnostic Cards & Fleet Reports (Spec 046).

Pure, deterministic renderers and keyboard builders for Telegram Mobile.
All data lines strictly adhere to visible_line_width <= 32 columns.
Zero I/O, zero database connections, zero threading locks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
)


# ── Callback Parser ───────────────────────────────────────────────────
@dataclass(frozen=True)
class DiagnosticCallbackAction:
    action: str  # e.g. "ref"
    report_type: str  # e.g. "status", "fans", "eff", "presets", "balancer", etc.


def parse_diagnostic_callback(callback_data: str) -> Optional[DiagnosticCallbackAction]:
    """Strictly parse and validate diagnostic callbacks (limit <= 64 bytes UTF-8)."""
    if not callback_data:
        return None
    if len(callback_data.encode("utf-8")) > 64:
        return None

    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "diag":
        return None

    action, report_type = parts[1], parts[2]
    if action != "ref":
        return None
    if report_type not in SUPPORTED_REPORT_TYPES:
        return None

    return DiagnosticCallbackAction(action=action, report_type=report_type)


# ── Keyboard Builder ──────────────────────────────────────────────────
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
    return build_inline_keyboard([
        [
            {"text": "🔄 Actualizar", "callback_data": ref_cb},
            {"text": "📱 Menú", "callback_data": CC_NAV_MAIN},
        ]
    ])


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
        pwm = getattr(st, "last_fan_duty_percent", None)
        power = getattr(st, "last_power_w", None)
        efficiency = getattr(st, "last_efficiency_j_th", None)
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
