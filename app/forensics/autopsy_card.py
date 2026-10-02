"""Mobile-First (<= 32 cols) card formatters for incident autopsy reports (Spec 086 / PROP-016)."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from app.forensics.autopsy_engine import (
    CAUSE_AUTOTUNE_STALL,
    CAUSE_CHAIN_BREAK,
    CAUSE_LINK_DROP,
    CAUSE_POWER_LOSS,
    CAUSE_PSU_FAULT,
    CAUSE_THERMAL_SHUTDOWN,
    CAUSE_UNRESOLVED,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    AutopsyReport,
)
from app.telegram.help_center import visible_line_width, wrap_mobile_lines

CARD_SEPARATOR = "─" * 30
MAX_CARD_LINE_WIDTH = 32

_CAUSE_HEADERS = {
    CAUSE_LINK_DROP: "⚠️ ENLACE ETHERNET",
    CAUSE_CHAIN_BREAK: "🔴 ROTURA CADENA",
    CAUSE_THERMAL_SHUTDOWN: "🔥 SOBRETEMPERATURA",
    CAUSE_PSU_FAULT: "⚡ FALLA DE PSU",
    CAUSE_AUTOTUNE_STALL: "⚙️ AUTOTUNE BLOQUEO",
    CAUSE_POWER_LOSS: "🔌 CORTE ELÉCTRICO",
    CAUSE_UNRESOLVED: "❓ NO DETERMINADA",
}

_CONFIDENCE_LABELS = {
    CONFIDENCE_HIGH: "ALTA",
    CONFIDENCE_MEDIUM: "MEDIA",
    CONFIDENCE_LOW: "BAJA",
}


def build_autopsy_card(report: AutopsyReport) -> str:
    """Build an executive mobile-first card adhering strictly to <= 32 columns per line."""
    time_str = datetime.fromtimestamp(report.timestamp).strftime("%H:%M:%S")
    conf_str = _CONFIDENCE_LABELS.get(report.confidence, report.confidence)
    cause_str = _CAUSE_HEADERS.get(report.root_cause_category, report.headline)

    lines: list[str] = [
        f"🔬 AUTOPSIA: {report.miner_name}"[:MAX_CARD_LINE_WIDTH],
        CARD_SEPARATOR,
        f"Hora: {time_str} | Certeza: {conf_str}"[:MAX_CARD_LINE_WIDTH],
        f"Causa: {cause_str}"[:MAX_CARD_LINE_WIDTH],
        CARD_SEPARATOR,
        "Evidencia Forense:",
    ]

    # Bullets
    for bullet in report.summary_bullets:
        bullet_lines = wrap_mobile_lines(
            bullet,
            width=MAX_CARD_LINE_WIDTH,
            indent="  ",
            first_indent="• ",
        )
        lines.extend(bullet_lines)

    lines.append(CARD_SEPARATOR)

    # Silicon health
    if report.is_silicon_healthy:
        lines.append("Silicio: ✅ SANO")
    else:
        lines.append("Silicio: ❌ FALLA DE CADENA")

    # Remediation
    lines.append("Acción recomendada:")
    remed_lines = wrap_mobile_lines(
        report.remediation_suggestion,
        width=MAX_CARD_LINE_WIDTH,
        indent="",
        first_indent="",
    )
    lines.extend(remed_lines)

    lines.append(CARD_SEPARATOR)

    # Final enforcement of <= 32 columns
    guaranteed_lines: list[str] = []
    for line in lines:
        if visible_line_width(line) <= MAX_CARD_LINE_WIDTH:
            guaranteed_lines.append(line)
        else:
            guaranteed_lines.extend(wrap_mobile_lines(line, width=MAX_CARD_LINE_WIDTH))

    return "\n".join(guaranteed_lines)


def build_fleet_autopsy_summary_card(reports: Sequence[AutopsyReport]) -> str:
    """Build a multi-miner executive summary adhering to <= 32 columns per line."""
    lines: list[str] = [
        "🔬 AUTOPSIAS FLOTA",
        CARD_SEPARATOR,
    ]

    if not reports:
        lines.extend([
            "Sin incidentes recientes.",
            "Flota operando nominal.",
            CARD_SEPARATOR,
        ])
        return "\n".join(lines)

    for rep in reports[:5]:
        time_str = datetime.fromtimestamp(rep.timestamp).strftime("%H:%M")
        cause_str = _CAUSE_HEADERS.get(rep.root_cause_category, rep.root_cause_category)
        silicon_str = "SANO" if rep.is_silicon_healthy else "FALLA"

        header_line = f"• {rep.miner_name} ({time_str})"
        lines.append(header_line[:MAX_CARD_LINE_WIDTH])

        lines.extend(wrap_mobile_lines(
            f"Causa: {cause_str}",
            width=MAX_CARD_LINE_WIDTH,
            indent="  ",
            first_indent="  ",
        ))
        lines.extend(wrap_mobile_lines(
            f"Silicio: {silicon_str} | Certeza: {_CONFIDENCE_LABELS.get(rep.confidence, rep.confidence)}",
            width=MAX_CARD_LINE_WIDTH,
            indent="  ",
            first_indent="  ",
        ))

    lines.append(CARD_SEPARATOR)
    lines.append("Usa /autopsia <id> x detalle")
    lines.append(CARD_SEPARATOR)

    guaranteed_lines: list[str] = []
    for line in lines:
        if visible_line_width(line) <= MAX_CARD_LINE_WIDTH:
            guaranteed_lines.append(line)
        else:
            guaranteed_lines.extend(wrap_mobile_lines(line, width=MAX_CARD_LINE_WIDTH))

    return "\n".join(guaranteed_lines)
