"""Telegram Mobile Help Center & Categorized Navigation (Spec 045).

Provides a pure, deterministic, I/O-free catalog and interactive UI for
all supported Telegram commands and categories.
All renderers and parsers in this module operate strictly in memory.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

HELP_PREFIX = "help:"
HELP_NAV_HOME = "help:nav:home"
MAX_CALLBACK_BYTES = 64
MAX_INTERACTIVE_VIEW_CHARS = 3600
MOBILE_LINE_WIDTH_LIMIT = 32


@dataclass(frozen=True)
class CommandDefinition:
    """Canonical definition of an operational command."""
    name: str
    summary: str
    usage: str
    category: str
    detail: List[str]
    examples: List[str]
    notes: List[str] = field(default_factory=list)
    danger_level: str = "safe"  # "safe" or "danger"
    aliases: List[str] = field(default_factory=list)
    official_aliases: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class HelpCategory:
    """Thematic grouping of commands for mobile navigation."""
    id: str
    title: str
    icon: str
    description: str
    command_names: List[str]


@dataclass(frozen=True)
class HelpAction:
    """Structured callback action from interactive inline buttons."""
    kind: str  # "nav", "cat", "cmd"
    target: str  # "home", category id (e.g. "thm"), or command name (e.g. "silent")


# ── Canonical Command Catalog ────────────────────────────────────────

HELP_COMMANDS: Dict[str, CommandDefinition] = {
    # ── Monitoreo (mon) ──
    "status": CommandDefinition(
        name="status",
        summary="Snapshot actual de la flota.",
        usage="/status",
        category="mon",
        detail=[
            "Muestra hashrate, temperaturas, consumo y estado en tiempo real.",
        ],
        examples=["/status"],
        danger_level="safe",
    ),
    "info": CommandDefinition(
        name="info",
        summary="Telemetría detallada o ayuda.",
        usage="/info [id|all|<comando>]",
        category="mon",
        detail=[
            "Muestra detalle de mineros con alertas, de un equipo o de un comando.",
        ],
        examples=["/info", "/info 23", "/info silent"],
        notes=["Algunos campos dependen del firmware."],
        danger_level="safe",
    ),
    "chart": CommandDefinition(
        name="chart",
        summary="Gráficos PNG de telemetría.",
        usage="/chart [id|grupo|fleet] [horas]",
        category="mon",
        detail=[
            "Genera curvas de hashrate, umbrales y temperaturas desde SQLite.",
            "Soporta grupos eléctricos (ej. elevator_1) y botones inline de rango.",
        ],
        examples=["/chart", "/chart 23", "/chart elevator_1", "/chart fleet 24h"],
        notes=["Renderizado visual 100% en memoria con selector inline 1h/6h/24h/7d."],
        danger_level="safe",
    ),
    "digest": CommandDefinition(
        name="digest",
        summary="Resumen ejecutivo 24h.",
        usage="/digest  |  /summary",
        category="mon",
        detail=[
            "Reporte consolidado: uptime, TH/s, J/TH, eventos y backups.",
        ],
        examples=["/digest", "/summary"],
        aliases=["summary"],
        danger_level="safe",
    ),

    # ── Térmico & Fans (thm) ──
    "fans": CommandDefinition(
        name="fans",
        summary="Salud de coolers y margen 85°C.",
        usage="/fans [id|all]",
        category="thm",
        detail=[
            "Supervisa RPM, PWM %, temperatura máxima y margen al corte.",
        ],
        examples=["/fans", "/fans 23"],
        aliases=["fan"],
        danger_level="safe",
    ),
    "governor": CommandDefinition(
        name="governor",
        summary="Regulador lazo cerrado (82°C).",
        usage="/gov [on|off|set <temp>]",
        category="thm",
        detail=[
            "Control térmico dinámico de coolers para temperatura estable.",
        ],
        examples=["/gov", "/gov on", "/gov off", "/gov set 82.0"],
        aliases=["gov"],
        notes=["Arranca en modo dry-run seguro."],
        danger_level="safe",
    ),
    "silent": CommandDefinition(
        name="silent",
        summary="Modo silencio (30-50% PWM).",
        usage="/silent <duración|off>",
        category="thm",
        detail=[
            "Régimen acústico reducido acotando PWM entre 30% y 50%.",
            "Guarda térmica reactiva ventiladores al 100% ante >80°C o fallas.",
        ],
        examples=["/silent 2h", "/silent 30m", "/silent off"],
        notes=["Duraciones: 30m, 1h, 2h, 4h, 6h, indef, off."],
        aliases=["silencio", "modo_silencio"],
        danger_level="safe",
    ),

    # ── Energía & Presets (pwr) ──
    "efficiency": CommandDefinition(
        name="efficiency",
        summary="Eficiencia en Joules por TH.",
        usage="/efficiency [id|all]",
        category="pwr",
        detail=[
            "Calcula J/TH en tiempo real (Watts / TH/s) y detecta anomalías.",
        ],
        examples=["/efficiency", "/efficiency 23", "/eff"],
        aliases=["eff"],
        danger_level="safe",
    ),
    "presets": CommandDefinition(
        name="presets",
        summary="Frecuencias, tensión y tuning.",
        usage="/presets [id|all]",
        category="pwr",
        detail=[
            "Supervisa frecuencias en MHz, tensión y calibración Vnish.",
        ],
        examples=["/presets", "/presets 23", "/preset", "/profile"],
        aliases=["preset", "profile"],
        danger_level="safe",
    ),
    "balancer": CommandDefinition(
        name="balancer",
        summary="Balanceador para elevadores.",
        usage="/balancer [on|off|miner]",
        category="pwr",
        detail=[
            "Optimiza presets contra reinicios por sensibilidad eléctrica.",
        ],
        examples=["/balancer", "/balancer on", "/balancer 23"],
        aliases=["bal", "power"],
        notes=["Arranca en dry-run seguro."],
        danger_level="safe",
    ),
    "elevadores": CommandDefinition(
        name="elevadores",
        summary="Diagnóstico de carga elevador.",
        usage="/elevadores",
        category="pwr",
        detail=[
            "Correlaciona Watts combinados y caídas en cascada por elevador.",
        ],
        examples=["/elevadores", "/sensibilidad"],
        aliases=["elevators", "sensibilidad", "elev"],
        danger_level="safe",
    ),

    # ── Control & Acciones (ctrl) ──
    "menu": CommandDefinition(
        name="menu",
        summary="Command Center interactivo.",
        usage="/menu  |  /start  |  /panel",
        category="ctrl",
        detail=[
            "Consola central táctil con métricas, perfiles y acciones.",
        ],
        examples=["/menu", "/start", "/panel"],
        aliases=["start", "panel"],
        danger_level="safe",
    ),
    "reboot": CommandDefinition(
        name="reboot",
        summary="Reinicio manual de un minero.",
        usage="/reboot <id>  |  /rb<id>",
        category="ctrl",
        detail=[
            "Solicita reinicio controlado mediante token de confirmación.",
        ],
        examples=["/reboot 23", "/rb23"],
        notes=["Confirmación obligatoria. Código expira en 60s."],
        official_aliases=["/rb<ID>"],
        danger_level="danger",
    ),
    "reboot_no_ok": CommandDefinition(
        name="reboot_no_ok",
        summary="Reinicio agrupado de NO-OK.",
        usage="/reboot_no_ok",
        category="ctrl",
        detail=[
            "Prepara preview acotado y código para mineros con problemas.",
        ],
        examples=["/reboot_no_ok"],
        notes=["Confirmar con atajo /c<code> recibido en preview."],
        danger_level="danger",
    ),
    "restart": CommandDefinition(
        name="restart",
        summary="Restart del software minero.",
        usage="/restart <id>",
        category="ctrl",
        detail=[
            "Reinicia cgminer/vnish sin reiniciar el sistema operativo.",
        ],
        examples=["/restart 23"],
        notes=["Requiere confirmación obligatoria."],
        danger_level="danger",
    ),
    "confirm": CommandDefinition(
        name="confirm",
        summary="Confirma acción pendiente.",
        usage="/confirm reboot <id> <code>  |  /c<code>",
        category="ctrl",
        detail=[
            "Valida token temporal y ejecuta la orden autorizada.",
        ],
        examples=["/confirm reboot 23 123456", "/c123456"],
        official_aliases=["/c<code>"],
        danger_level="danger",
    ),
    "snooze": CommandDefinition(
        name="snooze",
        summary="Pausa alertas por mantenimiento.",
        usage="/snooze <id|all> [minutos]",
        category="ctrl",
        detail=[
            "Suspende alertas y autorreinicios durante intervenciones.",
        ],
        examples=["/snooze 23 60", "/snooze all 30"],
        notes=["Por defecto 60 min (máx 1440m/24h)."],
        danger_level="safe",
    ),
    "unsnooze": CommandDefinition(
        name="unsnooze",
        summary="Reactiva supervisión normal.",
        usage="/unsnooze <id|all>",
        category="ctrl",
        detail=[
            "Cancela mantenimiento y reactiva alertas de inmediato.",
        ],
        examples=["/unsnooze 23", "/unsnooze all"],
        danger_level="safe",
    ),
    "snoozed": CommandDefinition(
        name="snoozed",
        summary="Lista mineros en mantenimiento.",
        usage="/snoozed",
        category="ctrl",
        detail=[
            "Muestra mineros pausados y tiempo restante de silencio.",
        ],
        examples=["/snoozed"],
        danger_level="safe",
    ),
    "shutdown": CommandDefinition(
        name="shutdown",
        summary="Parada segura y purga térmica.",
        usage="/shutdown [id1 id2... | all]",
        category="ctrl",
        detail=[
            "Detiene hashboards (0W) e inicia purga térmica activa de 45s.",
            "Aplica 4h de mantenimiento eléctrico sin falsas alarmas.",
        ],
        examples=["/shutdown", "/shutdown 23 25", "/shutdown all"],
        aliases=["stop", "apagar", "parada"],
        danger_level="danger",
    ),
    "resume": CommandDefinition(
        name="resume",
        summary="Reanudar minado tras parada.",
        usage="/resume [id1 id2... | all]",
        category="ctrl",
        detail=[
            "Reconecta tensión DC a hashboards e inicializa minado.",
            "Remueve automáticamente el estado de mantenimiento.",
        ],
        examples=["/resume", "/resume 23 25", "/resume all"],
        aliases=["reanudar"],
        danger_level="safe",
    ),
    "agent": CommandDefinition(
        name="agent",
        summary="Estado del agente supervisor.",
        usage="/agent [status|log]",
        category="ctrl",
        detail=[
            "Muestra el estado operativo del agente,",
            "última sincronización y ciclo de control.",
        ],
        examples=["/agent", "/agent status"],
        aliases=["agente", "fga"],
        danger_level="safe",
    ),

    # ── Diagnóstico & Eventos (diag) ──
    "events": CommandDefinition(
        name="events",
        summary="Historial reciente de incidentes.",
        usage="/events [id]",
        category="diag",
        detail=[
            "Consulta incidentes locales en SQLite sin tocar el minero.",
        ],
        examples=["/events", "/events 23"],
        danger_level="safe",
    ),
    "event": CommandDefinition(
        name="event",
        summary="Detalle de incidente por ID.",
        usage="/event <id>  |  /e<id>",
        category="diag",
        detail=[
            "Muestra clasificación y evidencia registrada del evento.",
        ],
        examples=["/event 42", "/e42"],
        official_aliases=["/e<ID>"],
        danger_level="safe",
    ),
    "why": CommandDefinition(
        name="why",
        summary="Explica último auto-reboot.",
        usage="/why [id]",
        category="diag",
        detail=[
            "Consulta evidencia y umbrales que motivaron la decisión.",
        ],
        examples=["/why", "/why 23"],
        danger_level="safe",
    ),
    "diagnose": CommandDefinition(
        name="diagnose",
        summary="Diagnóstico multidisciplinario.",
        usage="/diagnose [id|all]",
        category="diag",
        detail=[
            "Correlaciona telemetría, eventos SQLite y Vnish.",
        ],
        examples=["/diagnose", "/diagnose 23"],
        notes=["Es consultivo y no ejecuta acciones."],
        danger_level="safe",
    ),
    "health": CommandDefinition(
        name="health",
        summary="Comparación con baseline estable.",
        usage="/health [id|all]",
        category="diag",
        detail=[
            "Detecta desvíos de telemetría respecto al historial sano.",
        ],
        examples=["/health", "/health 23"],
        danger_level="safe",
    ),
    "quality": CommandDefinition(
        name="quality",
        summary="Calidad de minado y errores HW.",
        usage="/quality [id|all]",
        category="diag",
        detail=[
            "Supervisa shares, errores y estado de hashboards.",
        ],
        examples=["/quality", "/quality 23"],
        danger_level="safe",
    ),
    "firmware": CommandDefinition(
        name="firmware",
        summary="Evidencia de firmware Vnish.",
        usage="/firmware [id|all]",
        category="diag",
        detail=[
            "Consulta eventos de firmware recolectados en SQLite.",
        ],
        examples=["/firmware", "/firmware 23"],
        danger_level="safe",
    ),
    "selftest": CommandDefinition(
        name="selftest",
        summary="Chequeo rápido de subsistemas.",
        usage="/selftest  |  /test",
        category="diag",
        detail=[
            "Valida Telegram, Hashcore, SQLite y mineros.",
        ],
        examples=["/selftest", "/test"],
        aliases=["test"],
        danger_level="safe",
    ),
    "help": CommandDefinition(
        name="help",
        summary="Centro de ayuda y navegación.",
        usage="/help  |  /help <comando>",
        category="diag",
        detail=[
            "Abre el menú interactivo o muestra ayuda por comando.",
        ],
        examples=["/help", "/help silent", "/help reboot"],
        danger_level="safe",
    ),
    "chains": CommandDefinition(
        name="chains",
        summary="Salud y sensores por hashboard.",
        usage="/chains [id|all]",
        category="diag",
        detail=[
            "Supervisa temperatura, frecuencia, chips y sensores I2C de cada placa.",
            "Detecta fallas de sensor previas a cortes de cadena (chain break).",
        ],
        examples=["/chains", "/chains 24", "/chains all"],
        aliases=["chain", "placas"],
        danger_level="safe",
    ),
    "anomalias": CommandDefinition(
        name="anomalias",
        summary="Desglose de anomalías 24h.",
        usage="/anomalias [resumen|detalle]",
        category="diag",
        detail=[
            "Despliega las anomalías (warning/critical) del último informe diario.",
            "Opción 1 (/anomalias): 1 fila compacta por anomalía.",
            "Opción 2 (/anomalias detalle): descripción completa y enlace /e<id>.",
        ],
        examples=["/anomalias", "/anomalias detalle", "/anomalias 23"],
        aliases=["anomalies", "anom"],
        danger_level="safe",
    ),
    "autopsia": CommandDefinition(
        name="autopsia",
        summary="Autopsia forense post-mortem.",
        usage="/autopsia [id|all]",
        category="diag",
        detail=[
            "Investiga causa raíz de reinicios inesperados.",
            "Diagnóstico determinístico de red, cadena, PSU o calor.",
        ],
        examples=["/autopsia", "/autopsia 25", "/causa_raiz 24"],
        aliases=["causa_raiz", "autopsy", "investigar"],
        danger_level="safe",
    ),
    "directivas": CommandDefinition(
        name="directivas",
        summary="Políticas activas y gobernanza.",
        usage="/directivas [watchdog|grace|all]",
        category="diag",
        detail=[
            "Inspecciona el watchdog de deadlocks,",
            "período de gracia cold-boot y balanceo.",
        ],
        examples=["/directivas", "/directivas watchdog"],
        aliases=["gov_status", "directives", "directiva"],
        danger_level="safe",
    ),
}

HELP_CATEGORIES: Dict[str, HelpCategory] = {
    "mon": HelpCategory(
        id="mon",
        title="Monitoreo",
        icon="📊",
        description="Telemetría, estado y métricas",
        command_names=["status", "chart", "digest", "info"],
    ),
    "thm": HelpCategory(
        id="thm",
        title="Térmico & Fans",
        icon="🌡️",
        description="Coolers, lazo cerrado y silencio",
        command_names=["fans", "governor", "silent"],
    ),
    "pwr": HelpCategory(
        id="pwr",
        title="Energía & Presets",
        icon="⚡",
        description="Eficiencia, perfiles y elevadores",
        command_names=["efficiency", "presets", "balancer", "elevadores"],
    ),
    "ctrl": HelpCategory(
        id="ctrl",
        title="Control & Acciones",
        icon="🔄",
        description="Reinicios, menú y pausas",
        command_names=[
            "menu",
            "reboot",
            "reboot_no_ok",
            "restart",
            "confirm",
            "snooze",
            "unsnooze",
            "snoozed",
            "shutdown",
            "resume",
            "agent",
        ],
    ),
    "diag": HelpCategory(
        id="diag",
        title="Diagnóstico",
        icon="📜",
        description="Eventos, análisis y selftest",
        command_names=[
            "events",
            "autopsia",
            "anomalias",
            "event",
            "why",
            "diagnose",
            "health",
            "quality",
            "firmware",
            "selftest",
            "chains",
            "help",
            "directivas",
        ],
    ),
}

# Alias resolution mapping
_ALIAS_MAP: Dict[str, str] = {}
for _canonical_name, _cmd_def in HELP_COMMANDS.items():
    _ALIAS_MAP[_canonical_name.lower()] = _canonical_name
    for _alias in _cmd_def.aliases:
        _ALIAS_MAP[_alias.lower()] = _canonical_name


# ── Lookup & Parsing ─────────────────────────────────────────────────

def lookup_command(needle: str) -> Optional[CommandDefinition]:
    """Resolve a command name or alias to its canonical CommandDefinition."""
    if not needle:
        return None
    cleaned = str(needle).strip().lstrip("/").lower()
    canonical = _ALIAS_MAP.get(cleaned)
    if canonical and canonical in HELP_COMMANDS:
        return HELP_COMMANDS[canonical]
    return None


def parse_help_callback(raw_data: str) -> Optional[HelpAction]:
    """Parse callback_data starting with 'help:' into a structured HelpAction.

    Enforces strict grammar and maximum 64 bytes UTF-8 payload limit.
    Supported grammars:
    - help:nav:home
    - help:cat:<cat_id>   (e.g., help:cat:thm)
    - help:cmd:<cmd_name> (e.g., help:cmd:silent)
    """
    if not raw_data or not isinstance(raw_data, str):
        return None

    # Check 64 bytes limit
    if len(raw_data.encode("utf-8")) > MAX_CALLBACK_BYTES:
        return None

    if not raw_data.startswith(HELP_PREFIX):
        return None

    parts = raw_data.strip().split(":")
    if len(parts) != 3:
        return None

    _, kind, target = parts

    if kind == "nav":
        if target == "home":
            return HelpAction(kind="nav", target="home")
        return None

    if kind == "cat":
        if target in HELP_CATEGORIES:
            return HelpAction(kind="cat", target=target)
        return None

    if kind == "cmd":
        resolved = lookup_command(target)
        if resolved is not None:
            return HelpAction(kind="cmd", target=resolved.name)
        return None

    return None


# ── Formatting & Text Wrapping Helpers ───────────────────────────────

def strip_markdown(text: str) -> str:
    """Remove Markdown formatting characters (*, _, `, [) for width measurement."""
    if not text:
        return ""
    # Normalize unicode
    cleaned = unicodedata.normalize("NFC", text)
    # Replace escaped characters with placeholders first so they aren't stripped
    placeholders = {
        r"\*": "\u0001",
        r"\_": "\u0002",
        r"\`": "\u0003",
        r"\[": "\u0004",
        r"\]": "\u0005",
    }
    for esc, ph in placeholders.items():
        cleaned = cleaned.replace(esc, ph)
    # Remove unescaped markdown symbols
    cleaned = re.sub(r"[*_`\[\]]", "", cleaned)
    # Restore the literal characters that were escaped
    restore = {
        "\u0001": "*",
        "\u0002": "_",
        "\u0003": "`",
        "\u0004": "[",
        "\u0005": "]",
    }
    for ph, lit in restore.items():
        cleaned = cleaned.replace(ph, lit)
    return cleaned


def visible_line_width(line: str) -> int:
    """Calculate the visible character count of a line without Markdown tags."""
    stripped = strip_markdown(line)
    return len(stripped)


def escape_markdown(text: str) -> str:
    """Safely escape Markdown special characters (*, _, `, [) without double-escaping."""
    if not text:
        return ""
    # Escape single characters that are not already preceded by backslash
    escaped = re.sub(r"(?<!\\)([*_`\[])", r"\\\1", text)
    return escaped


def wrap_mobile_lines(
    text: str,
    width: int = MOBILE_LINE_WIDTH_LIMIT,
    indent: str = "",
    first_indent: Optional[str] = None,
) -> List[str]:
    """Wrap plain or simple text into lines strictly <= width characters."""
    if not text:
        return []
    result = []
    f_indent = first_indent if first_indent is not None else indent
    paragraphs = text.split("\n")
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            result.append("")
            continue
        words = p_clean.split(" ")
        current_indent = f_indent
        current_line = current_indent
        for w in words:
            candidate = f"{current_line} {w}" if current_line != current_indent else f"{current_indent}{w}"
            if visible_line_width(candidate) <= width:
                current_line = candidate
            else:
                if current_line.strip():
                    result.append(current_line)
                current_indent = indent
                current_line = f"{current_indent}{w}"
        if current_line.strip():
            result.append(current_line)
    return result


def _build_inline_keyboard(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    """Construct Telegram inline_keyboard payload."""
    return {"inline_keyboard": rows}


# ── Renderers ────────────────────────────────────────────────────────

def render_help_home() -> Tuple[str, Dict[str, Any]]:
    """Render the main categorized Help Center mobile dashboard."""
    lines = [
        "📖 *CENTRO DE AYUDA*",
        "─" * 28,
        "Supervisión S19j Pro (28 cmds)",
        "Selecciona una categoría táctil:",
        "",
        "• 📊 *Monitoreo*: Telemetría",
        "• 🌡️ *Térmico*: Fans y silencio",
        "• ⚡ *Energía*: Eficiencia/presets",
        "• 🔄 *Control*: Reinicios/pausas",
        "• 📜 *Diagnóstico*: Eventos/salud",
        "",
        "💡 _Usa /info <cmd> para ayuda._",
    ]
    text = "\n".join(lines)

    keyboard = _build_inline_keyboard([
        [
            {"text": "📊 Monitoreo", "callback_data": "help:cat:mon"},
            {"text": "🌡️ Térmico", "callback_data": "help:cat:thm"},
        ],
        [
            {"text": "⚡ Energía", "callback_data": "help:cat:pwr"},
            {"text": "🔄 Control", "callback_data": "help:cat:ctrl"},
        ],
        [
            {"text": "📜 Diagnóstico", "callback_data": "help:cat:diag"},
            {"text": "📱 Menú", "callback_data": "cc:nav:main"},
        ],
    ])

    return text, keyboard


def render_help_category(cat_key: str) -> Tuple[str, Dict[str, Any]]:
    """Render a category submenu with command list and quick buttons."""
    cat = HELP_CATEGORIES.get(cat_key)
    if not cat:
        # Fallback to home if category is unknown
        return render_help_home()

    lines = [
        f"{cat.icon} *{cat.title.upper()}*",
        "─" * 28,
    ]

    cmd_buttons: List[Dict[str, str]] = []
    for cmd_name in cat.command_names:
        cmd = HELP_COMMANDS.get(cmd_name)
        if not cmd:
            continue
        lines.append(f"• */{cmd.name}*")
        wrapped_summary = wrap_mobile_lines(cmd.summary, width=32, indent="  ")
        lines.extend(wrapped_summary)
        cmd_buttons.append({
            "text": f"/{cmd.name}",
            "callback_data": f"help:cmd:{cmd.name}",
        })

    lines.append("")
    lines.append("💡 _Toca un botón para ver uso:_")
    text = "\n".join(lines)

    # Arrange command buttons in pairs (2 per row)
    keyboard_rows: List[List[Dict[str, str]]] = []
    row: List[Dict[str, str]] = []
    for btn in cmd_buttons:
        row.append(btn)
        if len(row) == 2:
            keyboard_rows.append(row)
            row = []
    if row:
        keyboard_rows.append(row)

    # Navigation buttons at the bottom
    keyboard_rows.append([
        {"text": "⬅️ Ayuda", "callback_data": HELP_NAV_HOME},
        {"text": "📱 Menú", "callback_data": "cc:nav:main"},
    ])

    return text, _build_inline_keyboard(keyboard_rows)


def render_help_command_detail(cmd_name: str) -> Tuple[str, Dict[str, Any]]:
    """Render the vertical mobile card with full detail for a command."""
    cmd = lookup_command(cmd_name)
    if not cmd:
        err_lines = [
            "❓ *COMANDO DESCONOCIDO*",
            "─" * 28,
            f"El comando '{escape_markdown(cmd_name)}' no existe.",
            "Revisa las categorías en /help.",
        ]
        text = "\n".join(err_lines)
        kb = _build_inline_keyboard([
            [
                {"text": "📖 Volver a Ayuda", "callback_data": HELP_NAV_HOME},
                {"text": "📱 Menú", "callback_data": "cc:nav:main"},
            ]
        ])
        return text, kb

    lines = [
        f"📖 *COMANDO /{cmd.name.upper()}*",
        "─" * 28,
    ]
    lines.extend(wrap_mobile_lines(cmd.summary, width=32))
    lines.append("")
    lines.append("📋 *Uso:*")

    # Split usage alternatives if present
    usage_parts = cmd.usage.split("  |  ")
    for u_part in usage_parts:
        u_clean = u_part.strip()
        lines.extend(wrap_mobile_lines(f"`{u_clean}`", width=32))

    if cmd.detail:
        lines.append("")
        lines.append("ℹ️ *Qué hace:*")
        for d in cmd.detail:
            lines.extend(wrap_mobile_lines(d, width=32, indent="  ", first_indent="• "))

    if cmd.examples:
        lines.append("")
        lines.append("💡 *Ejemplos:*")
        for ex in cmd.examples:
            lines.extend(wrap_mobile_lines(f"`{ex}`", width=32, indent="  ", first_indent="• "))

    if cmd.aliases:
        lines.append("")
        aliases_str = ", ".join(f"/{a}" for a in cmd.aliases)
        lines.extend(wrap_mobile_lines(f"🔄 *Aliases:* {aliases_str}", width=32, indent="  "))

    if cmd.official_aliases:
        lines.append("")
        shortcuts_str = ", ".join(cmd.official_aliases)
        lines.extend(wrap_mobile_lines(f"⚡ *Atajos:* {shortcuts_str}", width=32, indent="  "))

    if cmd.notes:
        lines.append("")
        lines.append("📌 *Notas:*")
        for n in cmd.notes:
            lines.extend(wrap_mobile_lines(n, width=32, indent="  ", first_indent="• "))

    if cmd.danger_level != "safe":
        lines.append("")
        lines.append("⚠️ *Precaución:*")
        lines.append("• Acción crítica.")
        lines.append("• Confirma en 60s.")

    text = "\n".join(lines)

    cat_callback = f"help:cat:{cmd.category}"
    keyboard = _build_inline_keyboard([
        [
            {"text": "⬅️ Categoría", "callback_data": cat_callback},
            {"text": "📖 Ayuda", "callback_data": HELP_NAV_HOME},
        ],
        [
            {"text": "📱 Menú", "callback_data": "cc:nav:main"},
        ],
    ])

    return text, keyboard


# ── Legacy Renderers (Text-only fallback) ────────────────────────────

def render_legacy_help_index() -> str:
    """Render plain text help index for backwards compatibility."""
    lines = [
        "MINER ALERTS - AYUDA",
        "",
        "MONITOREO",
        "/status - Snapshot actual de la flota.",
        "/info [id|all] - Telemetría detallada o ayuda.",
        "/chart [id|fleet] [horas] - Gráficos PNG de telemetría.",
        "/digest - Resumen ejecutivo 24h.",
        "",
        "TÉRMICO Y FANS",
        "/fans [id|all] - Salud de coolers y margen 85°C.",
        "/gov [on|off|set] - Regulador lazo cerrado (82°C).",
        "/silent <duración|off> - Modo silencio (30-50% PWM).",
        "",
        "ENERGÍA Y PRESETS",
        "/efficiency [id|all] - Eficiencia en Joules por TH.",
        "/presets [id|all] - Frecuencias, tensión y tuning.",
        "/balancer [on|off|miner] - Balanceador para elevadores.",
        "/elevadores - Diagnóstico de carga elevador.",
        "",
        "CONTROL Y ACCIONES",
        "/menu - Command Center interactivo.",
        "/snooze <id|all> [min] - Pausa alertas por mantenimiento.",
        "/unsnooze <id|all> - Reactiva supervisión normal.",
        "/snoozed - Lista mineros en mantenimiento.",
        "/reboot <id> - Reinicio manual (confirmación).",
        "  Atajo: /rb<ID>",
        "/reboot_no_ok - Reinicio agrupado de NO-OK.",
        "/restart <id> - Restart del software minero.",
        "/confirm ... - Confirma acción pendiente.",
        "  Atajo: /c<code>",
        "",
        "DIAGNÓSTICO",
        "/events [id] - Historial reciente de incidentes.",
        "/event <id> - Detalle de incidente por ID.",
        "/why [id] - Explica último auto-reboot.",
        "/diagnose [id|all] - Diagnóstico multidisciplinario.",
        "/health [id|all] - Comparación con baseline estable.",
        "/quality [id|all] - Calidad de minado y errores HW.",
        "/firmware [id|all] - Evidencia de firmware Vnish.",
        "/selftest - Chequeo rápido de subsistemas.",
        "",
        "SISTEMA",
        "/help - Muestra este índice o menú interactivo.",
        "/info <comando> - Explica uso, ejemplos y precauciones.",
    ]
    return "\n".join(lines)


def render_legacy_help_detail(cmd_name: str) -> str:
    """Render plain text command detail for backwards compatibility."""
    cmd = lookup_command(cmd_name)
    if not cmd:
        return f"Comando '{cmd_name}' desconocido. Usa /help para ver la lista."

    lines = [
        f"/{cmd.name}",
        "",
        "Descripcion:",
        cmd.summary,
    ]
    if cmd.detail:
        lines.extend(["", "Que hace:", *cmd.detail[:3]])
    lines.extend(["", "Uso:", cmd.usage])
    if cmd.examples:
        lines.extend(["", "Ejemplos:", *cmd.examples[:3]])
    if cmd.aliases:
        lines.extend(["", "Aliases:", ", ".join(f"/{a}" for a in cmd.aliases)])
    if cmd.official_aliases:
        lines.extend(["", "Atajos oficiales:", *cmd.official_aliases])
    if cmd.notes:
        lines.extend(["", "Notas:", *cmd.notes[:3]])
    if cmd.danger_level != "safe":
        lines.extend([
            "",
            "Precaucion:",
            "La confirmacion expira en 60s y se pierde si reinicia el servicio.",
        ])
    return "\n".join(lines)


def _handle_help_callback(
    cb_query: dict,
    *,
    bot_token: str,
    cb_chat_id: Any,
    message_id: Optional[int],
    cb_id: str,
) -> None:
    """Handle Help Center callbacks (help:*) with instant ACK and in-place navigation (Spec 045 & 087)."""
    from app.miner_monitor import answer_callback_query, edit_message_text, log

    cb_data = cb_query.get("data") or ""
    action = parse_help_callback(cb_data)
    if not action:
        log(f"HELP_CB_PARSE_FAIL cb_id={cb_id} data={cb_data[:40]!r}")
        answer_callback_query(bot_token, cb_id, text="⚠️ Opción no reconocida.")
        return

    # Acknowledge immediately to clear the UI spinner (< 50ms)
    answer_callback_query(bot_token, cb_id)

    new_text: Optional[str] = None
    new_markup: Optional[Dict[str, Any]] = None

    if action.kind == "nav" and action.target == "home":
        new_text, new_markup = render_help_home()
    elif action.kind == "cat":
        new_text, new_markup = render_help_category(action.target)
    elif action.kind == "cmd":
        new_text, new_markup = render_help_command_detail(action.target)

    if message_id is not None and new_text and new_markup:
        edit_message_text(
            bot_token,
            str(cb_chat_id),
            message_id,
            new_text,
            reply_markup=new_markup,
            parse_mode="Markdown",
        )
_COMMANDS = [
    {
        "name": "help",
        "summary": "Muestra ayuda general o detallada.",
        "usage": "/help  |  /help <comando>",
        "detail": [
            "Detalle: lista comandos y muestra ayuda por comando.",
        ],
        "examples": ["/help reboot"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "status",
        "summary": "Snapshot actual de todos los mineros.",
        "usage": "/status",
        "detail": [
            "Detalle: muestra hashrate y etiquetas actuales.",
        ],
        "examples": ["/status"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "info",
        "summary": "Detalle resumido de mineros.",
        "usage": "/info  |  /info all  |  /info <miner>",
        "detail": [
            "Detalle: info de no-OK o del minero indicado.",
        ],
        "examples": ["/info", "/info all", "/info 23"],
        "notes": ["Algunos campos dependen del firmware."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "events",
        "summary": "Historial reciente de eventos e incidentes.",
        "usage": "/events  |  /events <miner>",
        "detail": [
            "Detalle: consulta eventos locales sin conectarse al minero.",
        ],
        "examples": ["/events", "/events 23"],
        "notes": ["Usa /event <id> para abrir un evento."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "event",
        "summary": "Detalle de un incidente registrado.",
        "usage": "/event <id>",
        "detail": [
            "Detalle: muestra evidencia y clasificacion del evento indicado.",
        ],
        "examples": ["/event 42"],
        "notes": ["Es de solo lectura."],
        "danger_level": "safe",
        "aliases": [],
        "official_aliases": ["/e<ID>"],
    },
    {
        "name": "why",
        "summary": "Explica la ultima decision de auto-reboot.",
        "usage": "/why  |  /why <miner>",
        "detail": [
            "Detalle: consulta evidencia local sin conectarse al minero.",
        ],
        "examples": ["/why", "/why 23"],
        "notes": ["El voltaje de cadena no representa voltaje AC de entrada."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "health",
        "summary": "Compara la telemetria con el baseline estable del minero.",
        "usage": "/health  |  /health all  |  /health <miner>",
        "detail": [
            "Detalle: diagnostico historico read-only sin conectarse al minero.",
        ],
        "examples": ["/health", "/health 23"],
        "notes": ["WATCH es evidencia para revisar; no ejecuta acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "quality",
        "summary": "Analiza shares, errores y estado de cadenas por intervalo.",
        "usage": "/quality  |  /quality all  |  /quality <miner>",
        "detail": [
            "Detalle: diagnostico historico read-only de calidad de minado.",
        ],
        "examples": ["/quality", "/quality 23"],
        "notes": ["Una transicion/autotune se observa; no ejecuta acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "firmware",
        "summary": "Muestra evidencia Vnish normalizada desde SQLite.",
        "usage": "/firmware  |  /firmware all  |  /firmware <miner>",
        "detail": [
            "Detalle: consulta eventos de firmware recolectados sin conectarse al minero.",
        ],
        "examples": ["/firmware", "/firmware 23"],
        "notes": ["Es de solo lectura y no ejecuta acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "diagnose",
        "summary": "Correlaciona evidencia operativa local por minero.",
        "usage": "/diagnose  |  /diagnose all  |  /diagnose <miner>",
        "detail": [
            "Detalle: combina senal, eventos, decisiones y Vnish desde SQLite.",
        ],
        "examples": ["/diagnose", "/diagnose 23"],
        "notes": ["Es advisory, de solo lectura y no autoriza acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "chart",
        "summary": "Genera y envia grafico visual PNG de telemetria.",
        "usage": "/chart  |  /chart <miner> [horas]  |  /chart fleet [horas]",
        "detail": [
            "Detalle: genera curvas de hashrate, umbral y temperaturas desde SQLite.",
        ],
        "examples": ["/chart", "/chart 23", "/chart fleet 24h"],
        "notes": ["Es visual, de solo lectura y se renderiza 100% en memoria."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "fans",
        "summary": "Monitorea RPM, PWM %, temperatura máxima y margen térmico.",
        "usage": "/fans  |  /fans all  |  /fans <miner>",
        "detail": [
            "Detalle: supervisa salud de ventiladores, saturación de flujo y margen hacia el corte de 85°C.",
        ],
        "examples": ["/fans", "/fans 23"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["fan"],
    },
    {
        "name": "chains",
        "summary": "Salud granular y sensores por placa/hashboard.",
        "usage": "/chains  |  /chains all  |  /chains <miner>",
        "detail": [
            "Detalle: diagnostico predictivo de silicio y bus de sensores I2C por cadena.",
        ],
        "examples": ["/chains", "/chains 24"],
        "notes": ["Identifica placas con sensores en error o deficit de hashrate."],
        "danger_level": "safe",
        "aliases": ["chain", "placas"],
    },
    {
        "name": "efficiency",
        "summary": "Analiza el consumo y ratio de eficiencia en Joules por Terahash (J/TH).",
        "usage": "/efficiency  |  /efficiency all  |  /efficiency <miner>",
        "detail": [
            "Detalle: calcula J/TH en tiempo real (Watts / TH/s) y detecta degradación eléctrica de cadenas.",
        ],
        "examples": ["/efficiency", "/efficiency 23", "/eff"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["eff"],
    },
    {
        "name": "presets",
        "summary": "Monitorea frecuencias (MHz), tensión (V) y estado de autotuning Vnish.",
        "usage": "/presets  |  /presets all  |  /presets <miner>",
        "detail": [
            "Detalle: supervisa perfiles de consumo/frecuencia inferidos y estado de calibración dinámica del firmware.",
        ],
        "examples": ["/presets", "/presets 23", "/preset", "/profile"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["preset", "profile"],
    },
    {
        "name": "governor",
        "summary": "Controlador térmico de lazo cerrado para coolers Vnish.",
        "usage": "/gov  |  /gov on  |  /gov off  |  /gov set <temp>",
        "detail": [
            "Detalle: supervisa y modula el % PWM para sostener temperatura objetivo estable evitando oscilaciones.",
        ],
        "examples": ["/gov", "/gov on", "/gov off", "/gov set 82.0"],
        "notes": ["Soporta modo dry-run para operar con total seguridad."],
        "danger_level": "safe",
        "aliases": ["gov"],
    },
    {
        "name": "balancer",
        "summary": "Balanceador dinámico de potencia y presets para protección de elevadores.",
        "usage": "/balancer  |  /balancer on  |  /balancer off  |  /balancer setmax <miner> <preset>",
        "detail": [
            "Detalle: optimiza presets Vnish contra reinicios por sensibilidad eléctrica y maximiza hashrate neto.",
        ],
        "examples": ["/balancer", "/balancer on", "/balancer 23", "/balancer setmax 23 2500W"],
        "notes": ["Arranca en dry-run seguro por defecto."],
        "danger_level": "safe",
        "aliases": ["bal", "power"],
    },
    {
        "name": "elevadores",
        "summary": "Diagnóstico de carga eléctrica y sensibilidad de elevadores de tensión.",
        "usage": "/elevadores",
        "detail": [
            "Detalle: correlaciona carga combinada (Watts), reinicios y caídas en cascada por elevador para encontrar la configuración óptima.",
        ],
        "examples": ["/elevadores", "/sensibilidad"],
        "notes": ["Es analítico y de solo lectura."],
        "danger_level": "safe",
        "aliases": ["elevators", "sensibilidad", "elev"],
    },
    {
        "name": "snooze",
        "summary": "Silencia alertas y autorreinicios por mantenimiento.",
        "usage": "/snooze <miner|all> [minutos]",
        "detail": [
            "Detalle: suspende temporalmente alertas y autorreinicios para tareas de mantenimiento.",
        ],
        "examples": ["/snooze 23 60", "/snooze all 30"],
        "notes": ["Por defecto 60 minutos (máx 1440m/24h)."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "unsnooze",
        "summary": "Reactiva la supervision normal de un minero silenciado.",
        "usage": "/unsnooze <miner|all>",
        "detail": [
            "Detalle: cancela el silenciamiento y reactiva alertas y autorreinicios inmediatamente.",
        ],
        "examples": ["/unsnooze 23", "/unsnooze all"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "snoozed",
        "summary": "Lista los mineros actualmente silenciados y tiempo restante.",
        "usage": "/snoozed",
        "detail": [
            "Detalle: muestra el estado de todos los mineros bajo mantenimiento.",
        ],
        "examples": ["/snoozed"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "digest",
        "summary": "Reporte ejecutivo 24h de salud, métricas y backups.",
        "usage": "/digest  |  /summary",
        "detail": [
            "Detalle: genera el resumen consolidado de las últimas 24 horas (uptime, TH/s, J/TH, shares, eventos, backup).",
        ],
        "examples": ["/digest", "/summary"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["summary"],
    },
    {
        "name": "selftest",
        "summary": "Chequeo rapido de Telegram/Hashcore/mineros.",
        "usage": "/selftest  |  /test",
        "detail": [
            "Detalle: valida conectividad y reporte basico.",
        ],
        "examples": ["/selftest"],
        "notes": [],
        "danger_level": "safe",
        "aliases": ["test"],
    },
    {
        "name": "reboot",
        "summary": "Solicita reboot manual (con confirmacion).",
        "usage": "/reboot  |  /reboot <miner>",
        "detail": [
            "Detalle: genera un codigo y pide confirmacion.",
        ],
        "examples": ["/rb23", "/reboot 23"],
        "notes": ["Siempre requiere confirmacion antes de ejecutar."],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": ["/rb<ID>"],
    },
    {
        "name": "reboot_no_ok",
        "summary": "Prepara un reboot agrupado de mineros NO-OK.",
        "usage": "/reboot_no_ok",
        "detail": [
            "Detalle: crea un preview acotado y un codigo; no ejecuta sin confirmacion.",
        ],
        "examples": ["/reboot_no_ok"],
        "notes": ["Confirmar con el atajo /c<code> recibido en el preview."],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": [],
    },
    {
        "name": "restart",
        "summary": "Solicita restart manual (con confirmacion).",
        "usage": "/restart <miner>",
        "detail": [
            "Detalle: genera un codigo y pide confirmacion.",
        ],
        "examples": ["/restart 23", "/confirm restart 23 123456"],
        "notes": [],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": [],
    },
    {
        "name": "confirm",
        "summary": "Confirma una accion pendiente.",
        "usage": "/confirm reboot <miner> <code>  |  /confirm restart <miner> <code>",
        "detail": [
            "Detalle: ejecuta la accion pendiente con codigo.",
        ],
        "examples": ["/confirm reboot 23 123456"],
        "notes": ["El atajo /c<code> confirma un preview de /reboot_no_ok."],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": ["/c<code>"],
    },
    {
        "name": "menu",
        "summary": "Command Center interactivo con botones.",
        "usage": "/menu  |  /start  |  /panel",
        "detail": [
            "Detalle: abre el panel de control táctil con métricas agregadas y accesos rápidos.",
        ],
        "examples": ["/menu", "/start"],
        "notes": [],
        "danger_level": "safe",
        "aliases": ["start", "panel"],
    },
    {
        "name": "silent",
        "summary": "Modo silencio para coolers (30-50% PWM).",
        "usage": "/silent <duración|off>",
        "detail": [
            "Detalle: limita ventiladores al 30%-50% con guarda térmica de reversión ante >80°C.",
        ],
        "examples": ["/silent 2h", "/silent off"],
        "notes": ["Duraciones: 30m, 1h, 2h, 4h, 6h, indef, off."],
        "danger_level": "safe",
        "aliases": ["silencio", "modo_silencio"],
    },
]




def _help_usage_for(cmd_name: str) -> Optional[str]:
    needle = (cmd_name or '').strip().lstrip('/').lower()
    for cmd in _COMMANDS:
        name = str(cmd.get('name', '')).lower()
        aliases = [a.lower() for a in cmd.get('aliases', [])]
        if needle == name or needle in aliases:
            return str(cmd.get('usage', '')).strip()
    return None

render_help_index = render_legacy_help_index
render_help_detail = render_legacy_help_detail
