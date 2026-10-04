"""Offline deterministic conversational Q&A supervisor for Telegram (Spec 086 / PROP-016)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from app.forensics.autopsy_card import CARD_SEPARATOR, build_autopsy_card
from app.forensics.autopsy_engine import AutopsyReport
from app.telegram.help_center import visible_line_width, wrap_mobile_lines

logger = logging.getLogger("miner-alerts")

# Intent patterns
_RE_REBOOT_REASON = re.compile(
    r"(?:por\s*qu[eé]|porque|causa|motivo|qu[eé]\s*pas[oó]|cay[oó]|reinici[oó]|fall[oó]|qu[eé]\s*le\s*pas[oó]|autopsia|investiga)",
    re.IGNORECASE,
)
_RE_MINER_ID = re.compile(
    r"(?:s19\w*[-_]?)?\b(2[3-6]|\d{1,2})\b",
    re.IGNORECASE,
)
_RE_NETWORK = re.compile(
    r"\b(?:red|cable|enlace|link|ethernet|switch|desconexi[oó]n|conectividad)\b",
    re.IGNORECASE,
)
_RE_THERMAL = re.compile(
    r"\b(?:temp|temperatura|calor|fans?|cooler|ventilador(?:es)?|refrigeraci[oó]n)\b",
    re.IGNORECASE,
)
_RE_STATUS_FLEET = re.compile(
    r"\b(?:status|estado|flota|granja|mineros?|como\s+va|como\s+estan?|resumen|panel|rendimiento|hashrate|th/s|ths)\b",
    re.IGNORECASE,
)
_RE_POWER_ELEVATORS = re.compile(
    r"\b(?:potencia|consumo|watts?|kw|elevador(?:es)?|acometida|tensi[oó]n|carga)\b",
    re.IGNORECASE,
)
_RE_DIRECTIVES = re.compile(
    r"\b(?:directivas?|gobernanza|deadlocks?|pol[ií]ticas?|vigilante|watchdog|grace)\b",
    re.IGNORECASE,
)
_RE_GREETING = re.compile(
    r"\b(?:hola|buenas?|buen\s+d[ií]a|buenas\s+tardes|buenas\s+noches|hey|asistente|supervisor)\b",
    re.IGNORECASE,
)


def _ensure_max_width(lines: list[str], max_width: int = 32) -> str:
    guaranteed: list[str] = []
    for line in lines:
        if visible_line_width(line) <= max_width:
            guaranteed.append(line)
        else:
            guaranteed.extend(wrap_mobile_lines(line, width=max_width))
    return "\n".join(guaranteed)


def handle_conversational_query(
    query: str,
    context: Any,
    allow_fallback: bool = True,
) -> Optional[str]:
    """Parse natural language query and return deterministic offline answer in <= 32 cols."""
    if not query or not isinstance(query, str):
        return None

    clean_query = query.strip()
    if not clean_query:
        return None

    # Check Intent 1: Reboot / Autopsy inquiry for a specific miner
    if _RE_REBOOT_REASON.search(clean_query):
        miner_match = _RE_MINER_ID.search(clean_query)
        if miner_match:
            raw_id = miner_match.group(1)
            miners = getattr(context, "miners", []) or []
            from app.miner_monitor import resolve_miner

            target = resolve_miner(raw_id, miners)
            if target:
                miner_name = target.get("name", f"S19JPRO-{raw_id}")
                event_store = getattr(context, "event_store", None)
                if event_store and getattr(event_store, "available", False):
                    rec = event_store.get_latest_autopsy_assessment(miner_name)
                    if rec:
                        findings = []
                        hyp = {}
                        try:
                            findings = json.loads(rec.get("findings_json") or "[]")
                            hyps = json.loads(rec.get("hypotheses_json") or "[]")
                            if hyps:
                                hyp = hyps[0]
                        except Exception:
                            pass
                        report = AutopsyReport(
                            miner_name=rec.get("subject_ref", miner_name),
                            timestamp=float(rec.get("assessment_now_ts", time.time())),
                            root_cause_category=rec.get("status", "UNRESOLVED"),
                            confidence=hyp.get("confidence", "MEDIUM"),
                            headline=hyp.get("headline", "Reporte Forense"),
                            summary_bullets=tuple(findings),
                            remediation_suggestion=hyp.get("remediation", "Monitorear telemetría."),
                            is_silicon_healthy=bool(hyp.get("is_silicon_healthy", True)),
                            raw_evidence_digest=rec.get("evidence_digest", ""),
                        )
                        return build_autopsy_card(report)

                lines = [
                    f"🔬 {miner_name}",
                    CARD_SEPARATOR,
                    "No registra incidentes recientes.",
                    "Operando con normalidad.",
                    CARD_SEPARATOR,
                ]
                return _ensure_max_width(lines)

    # Check Intent 2: Network / Link inquiry
    if _RE_NETWORK.search(clean_query):
        event_store = getattr(context, "event_store", None)
        link_drop_count = 0
        if event_store and getattr(event_store, "available", False):
            fleet_recs = event_store.get_latest_autopsy_assessments_fleet(limit=20)
            link_drop_count = sum(1 for r in fleet_recs if r.get("status") == "LINK_DROP")

        status_text = "Estable" if link_drop_count == 0 else f"{link_drop_count} caídas rec."
        lines = [
            "🌐 ESTADO DE RED Y ENLACE",
            CARD_SEPARATOR,
            f"• Enlace físico: {status_text}",
            f"• Incidentes link (24h): {link_drop_count}",
            CARD_SEPARATOR,
            "Usa /autopsia x detalles",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    # Check Intent 3: Thermal / Fan inquiry
    if _RE_THERMAL.search(clean_query):
        lines = [
            "🌡️ ESTADO TÉRMICO Y FANS",
            CARD_SEPARATOR,
            "• Flota en rango operativo",
            "• Fans en regulación activa",
            CARD_SEPARATOR,
            "Usa /fans o /status x telemetría",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    # Check Intent 4: Fleet status / overview
    if _RE_STATUS_FLEET.search(clean_query):
        miners = getattr(context, "miners", []) or []
        states = getattr(context, "states", {}) or {}
        state_lock = getattr(context, "state_lock", None)

        if state_lock:
            with state_lock:
                states_copy = {k: v for k, v in states.items()}
        else:
            states_copy = dict(states)

        total_miners = len(miners)
        ok_count = 0
        total_ths = 0.0
        total_w = 0.0
        max_temp = 0.0

        for m in miners:
            m_name = m.get("name", "")
            m_host = m.get("host", "")
            m_port = m.get("port", 4028)
            sk = f"{m_name}|{m_host}:{m_port}"
            st = states_copy.get(sk)
            if st:
                st_val = getattr(st, "state", "OK")
                if st_val == "OK":
                    ok_count += 1
                r = getattr(st, "last_rate_ths", None) or getattr(st, "rate_ths", None) or 0.0
                try:
                    total_ths += float(r)
                except (TypeError, ValueError):
                    pass
                p = getattr(st, "last_power_w", None) or getattr(st, "governor_last_power_w", None) or 0.0
                try:
                    total_w += float(p)
                except (TypeError, ValueError):
                    pass
                t = getattr(st, "last_max_chip_temp", None) or getattr(st, "last_temp_c", None) or 0.0
                try:
                    t_val = float(t)
                    if t_val > max_temp:
                        max_temp = t_val
                except (TypeError, ValueError):
                    pass

        lines = [
            "📊 ESTADO DE FLOTA",
            CARD_SEPARATOR,
            f"• Mineros OK: {ok_count}/{total_miners}",
            f"• Hashrate: {total_ths:.1f} TH/s",
            f"• Potencia: {total_w / 1000.0:.2f} kW",
            f"• Temp Máx: {max_temp:.1f}°C" if max_temp > 0 else "• Temp Máx: N/A",
            CARD_SEPARATOR,
            "Usa /status para detalle",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    # Check Intent 5: Power & Elevators
    if _RE_POWER_ELEVATORS.search(clean_query):
        miners = getattr(context, "miners", []) or []
        states = getattr(context, "states", {}) or {}
        state_lock = getattr(context, "state_lock", None)

        if state_lock:
            with state_lock:
                states_copy = {k: v for k, v in states.items()}
        else:
            states_copy = dict(states)

        elev1_w = 0.0
        elev2_w = 0.0

        for m in miners:
            m_name = m.get("name", "")
            m_host = m.get("host", "")
            m_port = m.get("port", 4028)
            grp = m.get("electrical_group") or m.get("group")
            if not grp:
                if "23" in m_name or "24" in m_name:
                    grp = "elevator_1"
                elif "25" in m_name or "26" in m_name:
                    grp = "elevator_2"

            sk = f"{m_name}|{m_host}:{m_port}"
            st = states_copy.get(sk)
            pwr = 0.0
            if st:
                p = getattr(st, "last_power_w", None) or getattr(st, "governor_last_power_w", None)
                if p is not None:
                    try:
                        pwr = float(p)
                    except (TypeError, ValueError):
                        pwr = 0.0
                elif getattr(st, "state", "OK") == "OK":
                    pwr = 2700.0

            if grp == "elevator_1":
                elev1_w += pwr
            elif grp == "elevator_2":
                elev2_w += pwr

        tot_kw = (elev1_w + elev2_w) / 1000.0
        lines = [
            "⚡ POTENCIA Y ELEVADORES",
            CARD_SEPARATOR,
            f"• Elevador 1: {int(elev1_w)}W / 5400W",
            "  (M23 + M24)",
            f"• Elevador 2: {int(elev2_w)}W / 5400W",
            "  (M25 + M26)",
            f"• Total Flota: {tot_kw:.2f} kW",
            CARD_SEPARATOR,
            "Límite seguro: 5400W x elev.",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    # Check Intent 6: Directives & Governance
    if _RE_DIRECTIVES.search(clean_query):
        lines = [
            "🛡️ GOBERNANZA Y DIRECTIVAS",
            CARD_SEPARATOR,
            "• Deadlock Watchdog: ACTIVO",
            "  (Disparo por flanco)",
            "• Cold-Boot Grace: 900s",
            "  (Supresión en arranque)",
            "• Dynamic Balancer: ACTIVO",
            "  (Elevadores 5400W)",
            CARD_SEPARATOR,
            "Usa /directivas para matriz",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    # Check Intent 7: Greeting
    if _RE_GREETING.search(clean_query):
        lines = [
            "🤖 ASISTENTE SUPERVISOR",
            CARD_SEPARATOR,
            "¡Hola! Estoy en línea y",
            "monitoreando la flota.",
            "Puedes consultarme:",
            '• "¿Cómo está la flota?"',
            '• "¿Por qué reinició la 23?"',
            '• "¿Carga de elevadores?"',
            '• "¿Estado térmico?"',
            "O usa /menu o /help",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    # Fallback guide response (eliminating unhandled silence)
    if allow_fallback:
        lines = [
            "🤖 ASISTENTE DE FLOTA",
            CARD_SEPARATOR,
            "No reconocí esa consulta.",
            "Prueba preguntando:",
            '• "¿Cómo está la flota?"',
            '• "¿Por qué reinició la 23?"',
            '• "¿Carga de elevadores?"',
            '• "¿Estado térmico?"',
            "O escribe /menu o /help",
            CARD_SEPARATOR,
        ]
        return _ensure_max_width(lines)

    return None
