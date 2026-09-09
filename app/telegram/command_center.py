"""Telegram Interactive Command Center & Rich UI (Spec 043).

Provides pure formatting, layout templates, and InlineKeyboardMarkup builders
for the 1-2 click interactive mobile dashboard (/menu).
All functions in this module are strictly deterministic and free of network I/O.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Command Center Callback Prefixes and Actions
CC_PREFIX = "cc:"
CC_NAV_PREFIX = "cc:nav:"
CC_ACT_PREFIX = "cc:act:"

CC_NAV_MAIN = "cc:nav:main"
CC_NAV_METRICS = "cc:nav:metrics"
CC_NAV_REBOOT = "cc:nav:reboot"
CC_NAV_PROFILES = "cc:nav:profiles"
CC_NAV_ALERTS = "cc:nav:alerts"
CC_NAV_SILENT = "cc:nav:silent"
CC_ACT_REFRESH = "cc:act:refresh"


@dataclass(frozen=True)
class CommandCenterAction:
    kind: str  # "nav" or "act"
    target: str  # "main", "metrics", "reboot", "rb_req", "rb_cfm", "silent", etc.
    miner_id: Optional[str] = None
    token: Optional[str] = None
    param: Optional[str] = None


def parse_command_center_callback(raw_data: str) -> Optional[CommandCenterAction]:
    """Parse callback_data starting with 'cc:' into a structured CommandCenterAction.
    
    Supported grammars:
    - cc:nav:<target>                  (e.g., cc:nav:main, cc:nav:metrics, cc:nav:reboot, cc:nav:silent)
    - cc:act:refresh                   (refresh current dashboard)
    - cc:act:refresh:<view>            (refresh specific view)
    - cc:act:silent:<duration_key>     (activate or deactivate silent mode: 30m, 1h, 2h, 4h, 6h, indef, off)
    - cc:act:rb_req:<miner_id>         (request reboot confirmation)
    - cc:act:rb_cfm:<token>:<miner_id> (confirm reboot with token)
    - cc:act:rb_ccl:<miner_id>         (cancel reboot, return to reboot list)
    """
    if not raw_data or not raw_data.startswith(CC_PREFIX):
        return None

    parts = raw_data.strip().split(":")
    if len(parts) < 3:
        return None

    kind = parts[1]  # "nav" or "act"
    action = parts[2]  # "main", "metrics", "reboot", "refresh", "rb_req", "silent", etc.

    if kind == "nav":
        return CommandCenterAction(kind="nav", target=action)

    if kind == "act":
        if action == "refresh":
            view = parts[3] if len(parts) > 3 else "main"
            return CommandCenterAction(kind="act", target="refresh", param=view)
        elif action == "silent" and len(parts) >= 4:
            return CommandCenterAction(kind="act", target="silent", param=parts[3])
        elif action == "rb_req" and len(parts) >= 4:
            return CommandCenterAction(kind="act", target="rb_req", miner_id=parts[3])
        elif action == "rb_ccl" and len(parts) >= 4:
            return CommandCenterAction(kind="act", target="rb_ccl", miner_id=parts[3])
        elif action == "rb_cfm" and len(parts) >= 5:
            return CommandCenterAction(
                kind="act",
                target="rb_cfm",
                token=parts[3],
                miner_id=parts[4],
            )

    return None


def build_inline_keyboard(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    """Build a standard Telegram inline_keyboard payload dictionary."""
    return {"inline_keyboard": rows}


def make_progress_bar(val: float, max_val: float, width: int = 8) -> str:
    """Render a compact unicode visual progress bar."""
    if max_val <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, val / max_val))
    filled = int(round(ratio * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def render_main_dashboard(
    states: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render the executive Command Center main dashboard (/menu)."""
    miners_list = miners or (config.get("miners", []) if config else [])
    total_miners = len(miners_list) if miners_list else len(states)

    ok_count = 0
    offline_count = 0
    low_count = 0
    hashboard_count = 0
    total_hashrate = 0.0
    total_power = 0.0
    max_temp = 0.0
    duties: List[int] = []

    for miner in miners_list:
        m_id = str(miner.get("name") or miner.get("ip") or "")
        st = states.get(m_id)
        if not st:
            continue

        st_name = getattr(st, "state", "OK")
        if st_name == "OK":
            ok_count += 1
        elif st_name == "LOW":
            low_count += 1
        elif st_name == "OFFLINE":
            offline_count += 1
        elif st_name == "HASHBOARD":
            hashboard_count += 1

        # Check temperatures and duties from state
        t = getattr(st, "governor_last_temp_c", None)
        if t is not None and t > max_temp:
            max_temp = t

        p = getattr(st, "governor_last_power_w", None)
        if p is not None:
            total_power += p

        d = getattr(st, "governor_duty", None)
        if d is not None:
            duties.append(d)

    # State banner
    if offline_count > 0 or hashboard_count > 0:
        status_line = f"🔴 ATENCIÓN: {ok_count}/{total_miners} Minando ({offline_count + hashboard_count} con problemas)"
    elif low_count > 0:
        status_line = f"🟡 ADVERTENCIA: {ok_count}/{total_miners} Normales ({low_count} bajo TH/s)"
    else:
        status_line = f"🟢 ESTADO: Todos Minando ({ok_count}/{total_miners})"

    duty_str = f"{min(duties)}% - {max(duties)}%" if duties else "Auto / Stock"
    temp_str = f"{max_temp:.1f}°C" if max_temp > 0 else "Normal (<80°C)"
    power_str = f"{total_power:,.0f} W" if total_power > 0 else "N/A"

    lines = [
        "╔══════════════════════════════════════╗",
        "║   ⛏️ MINER-ALERTS COMMAND CENTER    ║",
        "╚══════════════════════════════════════╝",
        "",
        status_line,
        f"⚡ Potencia Total: {power_str}",
        f"🌡️ Temp Max: {temp_str}  |  🌪️ Fans: {duty_str}",
        "",
        "👇 *Selecciona una opción táctil:*",
    ]
    text = "\n".join(lines)

    any_silent = any(getattr(st, "silent_mode_active", False) for st in states.values())
    silent_btn_text = "🔊 Desactivar Silencio" if any_silent else "🔇 Modo Silencio"

    keyboard = build_inline_keyboard([
        [
            {"text": "📊 Métricas Flota", "callback_data": CC_NAV_METRICS},
            {"text": "⚙️ Presets / Perfiles", "callback_data": CC_NAV_PROFILES},
        ],
        [
            {"text": silent_btn_text, "callback_data": CC_NAV_SILENT},
            {"text": "🔄 Reinicios", "callback_data": CC_NAV_REBOOT},
        ],
        [
            {"text": "🔔 Alertas / Umbrales", "callback_data": CC_NAV_ALERTS},
            {"text": "🔄 Actualizar Panel", "callback_data": CC_ACT_REFRESH},
        ],
    ])

    return text, keyboard


def render_metrics_view(
    states: Dict[str, Any],
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render detailed metrics view with visual progress bars."""
    lines = [
        "📊 *MÉTRICAS DETALLADAS DE FLOTA*",
        "─" * 32,
    ]

    miners_list = miners or []
    if not miners_list and states:
        miners_list = [{"name": k} for k in states.keys()]

    for miner in miners_list:
        m_id = str(miner.get("name") or miner.get("ip") or "")
        st = states.get(m_id)
        if not st:
            continue

        st_name = getattr(st, "state", "OK")
        icon = "🟢" if st_name == "OK" else ("🟡" if st_name == "LOW" else "🔴")

        t = getattr(st, "governor_last_temp_c", None)
        temp_val = t if t is not None else 0.0
        bar = make_progress_bar(temp_val, 85.0, width=6)
        temp_display = f"{temp_val:.1f}°C" if t is not None else "N/A"

        duty = getattr(st, "governor_duty", None)
        duty_display = f"{duty}%" if duty is not None else "Auto"

        p = getattr(st, "governor_last_power_w", None)
        power_display = f"{p:.0f}W" if p is not None else "N/A"

        lines.append(f"{icon} *{m_id}*: [{bar}] {temp_display}")
        lines.append(f"   └ Fans: {duty_display} | Consumo: {power_display} | Estado: {st_name}")
        lines.append("")

    lines.append("─" * 32)

    keyboard = build_inline_keyboard([
        [
            {"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN},
            {"text": "🔄 Actualizar", "callback_data": f"{CC_ACT_PREFIX}refresh:metrics"},
        ]
    ])

    return "\n".join(lines), keyboard


def render_reboot_menu(
    states: Dict[str, Any],
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render reboot selection menu with 1-tap targets."""
    lines = [
        "🔄 *CONTROL DE REINICIOS*",
        "",
        "Selecciona el minero que deseas reiniciar.",
        "⚠️ *Seguridad*: Toda acción requerirá confirmación previa.",
        "─" * 32,
    ]

    miners_list = miners or []
    if not miners_list and states:
        miners_list = [{"name": k} for k in states.keys()]

    rows: List[List[Dict[str, str]]] = []
    current_row: List[Dict[str, str]] = []

    for miner in miners_list:
        m_id = str(miner.get("name") or miner.get("ip") or "")
        btn = {"text": f"🔄 Reiniciar {m_id}", "callback_data": f"{CC_ACT_PREFIX}rb_req:{m_id}"}
        current_row.append(btn)
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    rows.append([{"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN}])

    keyboard = build_inline_keyboard(rows)
    return "\n".join(lines), keyboard


def render_reboot_confirmation(miner_id: str, token: str) -> Tuple[str, Dict[str, Any]]:
    """Render safe 2-step confirmation dialog with ephemeral token."""
    text = (
        f"⚠️ *CONFIRMACIÓN DE REINICIO*\n\n"
        f"¿Estás seguro de que deseas reiniciar *{miner_id}*?\n"
        f"Esta acción enviará la orden de reinicio inmediato.\n"
        f"⏱️ _Esta confirmación expira en 60 segundos._"
    )
    keyboard = build_inline_keyboard([
        [
            {
                "text": f"✅ Sí, Confirmar Reinicio {miner_id}",
                "callback_data": f"{CC_ACT_PREFIX}rb_cfm:{token}:{miner_id}",
            }
        ],
        [
            {
                "text": "❌ Cancelar",
                "callback_data": f"{CC_ACT_PREFIX}rb_ccl:{miner_id}",
            }
        ],
    ])
    return text, keyboard


def render_profiles_view(
    states: Dict[str, Any],
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render presets and dynamic balancer status."""
    lines = [
        "⚙️ *PRESETS Y PERFILES DE POTENCIA*",
        "─" * 32,
    ]

    miners_list = miners or []
    if not miners_list and states:
        miners_list = [{"name": k} for k in states.keys()]

    for miner in miners_list:
        m_id = str(miner.get("name") or miner.get("ip") or "")
        st = states.get(m_id)
        preset = getattr(st, "balancer_preset", None) or "Stock / Normal"
        reason = getattr(st, "balancer_last_reason", "") or "Estable"
        lines.append(f"⛏️ *{m_id}*: Preset `{preset}`")
        if reason:
            lines.append(f"   └ Info: {reason}")

    lines.append("─" * 32)

    keyboard = build_inline_keyboard([
        [
            {"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN},
            {"text": "🔄 Actualizar", "callback_data": f"{CC_ACT_PREFIX}refresh:profiles"},
        ]
    ])
    return "\n".join(lines), keyboard


def render_alerts_view(
    states: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render alert thresholds and snooze statuses."""
    lines = [
        "🔔 *ESTADO DE ALERTAS Y SNOOZE*",
        "─" * 32,
    ]

    miners_list = miners or []
    if not miners_list and states:
        miners_list = [{"name": k} for k in states.keys()]

    now = time.time()
    for miner in miners_list:
        m_id = str(miner.get("name") or miner.get("ip") or "")
        st = states.get(m_id)
        snooze_until = getattr(st, "snooze_until_ts", None)
        if snooze_until and snooze_until > now:
            remaining_mins = int((snooze_until - now) / 60)
            snz_str = f"🔕 Silenciado ({remaining_mins}m restantes)"
        else:
            snz_str = "🔔 Alertas Activas"
        lines.append(f"• *{m_id}*: {snz_str}")

    lines.append("─" * 32)

    keyboard = build_inline_keyboard([
        [
            {"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN},
            {"text": "🔄 Actualizar", "callback_data": f"{CC_ACT_PREFIX}refresh:alerts"},
        ]
    ])
    return "\n".join(lines), keyboard


def render_silent_mode_view(
    states: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    miners: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render interactive Modo Silencio duration selector and status."""
    sm_target_max = int((config or {}).get("silent_mode_target_max_duty", 70))
    sm_min = int((config or {}).get("silent_mode_min_duty_pct", 40))
    emergency_temp = float((config or {}).get("fan_governor_emergency_temp_c", 83.5))

    miners_list = miners or []
    if not miners_list and states:
        miners_list = [{"name": k} for k in states.keys()]

    now = time.time()
    active_count = 0
    total_count = len(miners_list)
    status_lines = []

    for miner in miners_list:
        m_id = str(miner.get("name") or miner.get("ip") or "")
        st = states.get(m_id)
        if st and getattr(st, "silent_mode_active", False):
            active_count += 1
            revert_ts = getattr(st, "silent_mode_revert_ts", None)
            if revert_ts is not None:
                rem_m = max(0, int((revert_ts - now) // 60))
                rem_str = f"{rem_m}m restantes" if rem_m < 60 else f"{rem_m // 60}h {rem_m % 60}m restantes"
            else:
                rem_str = "indefinido"
            status_lines.append(f"  🔇 *{m_id}*: ACTIVO ({rem_str}, max {getattr(st, 'silent_mode_target_max_duty', sm_target_max)}%)")
        else:
            status_lines.append(f"  🔊 *{m_id}*: Normal (sin límite)")

    if active_count > 0:
        header_status = f"🔇 *ESTADO*: ACTIVO en {active_count}/{total_count} mineros"
    else:
        header_status = "🔊 *ESTADO*: Inactivo (ventilación normal)"

    lines = [
        "🔇 *MODO SILENCIO / VISITAS*",
        "─" * 32,
        header_status,
        f"Límite acústico: {sm_min}% a {sm_target_max}% PWM",
        f"🛡️ Guardián Térmico: Anulación automática si T ≥ {emergency_temp:.1f}°C",
        "",
        *status_lines,
        "",
        "👇 *Selecciona la duración para activar o cambiar:*",
    ]

    buttons = [
        [
            {"text": "⏱️ 30 min", "callback_data": f"{CC_ACT_PREFIX}silent:30m"},
            {"text": "⏱️ 1 hora", "callback_data": f"{CC_ACT_PREFIX}silent:1h"},
            {"text": "⏱️ 2 horas", "callback_data": f"{CC_ACT_PREFIX}silent:2h"},
        ],
        [
            {"text": "⏱️ 4 horas", "callback_data": f"{CC_ACT_PREFIX}silent:4h"},
            {"text": "⏱️ 6 horas", "callback_data": f"{CC_ACT_PREFIX}silent:6h"},
            {"text": "♾️ Indefinido", "callback_data": f"{CC_ACT_PREFIX}silent:indef"},
        ],
    ]

    if active_count > 0:
        buttons.append([{"text": "🛑 Desactivar Modo Silencio", "callback_data": f"{CC_ACT_PREFIX}silent:off"}])

    buttons.append([
        {"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN},
        {"text": "🔄 Actualizar", "callback_data": f"{CC_ACT_PREFIX}refresh:silent"},
    ])

    return "\n".join(lines), build_inline_keyboard(buttons)


def build_alert_action_buttons(miner_id: str) -> Dict[str, Any]:
    """Build actionable inline buttons for incident/episode alerts (RF-3)."""
    return build_inline_keyboard([
        [
            {"text": "🩺 Diagnóstico", "callback_data": f"diag:{miner_id}"},
            {"text": "📊 Ver Gráfico", "callback_data": f"chart:{miner_id}"},
        ],
        [
            {"text": f"🔄 Reiniciar {miner_id}", "callback_data": f"rb_req:{miner_id}"},
            {"text": "🔕 Silenciar 1h", "callback_data": f"snz:{miner_id}:60"},
        ],
    ])
