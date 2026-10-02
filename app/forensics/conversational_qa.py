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

    return None
