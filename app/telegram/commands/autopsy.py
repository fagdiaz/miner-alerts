"""Incident Autopsy Telegram Command Handler (Spec 086 / PROP-016)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, List, Optional

from app.forensics.autopsy_card import build_autopsy_card, build_fleet_autopsy_summary_card
from app.forensics.autopsy_engine import AutopsyReport
from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class AutopsyCommand(BaseCommandHandler):
    """Command handler for forensic incident autopsy inspection."""

    name = "autopsia"
    aliases = ["causa_raiz", "autopsy", "investigar"]
    description = "Autopsia forense y diagnóstico de causa raíz de incidentes recientes."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import resolve_miner

        event_store = context.event_store
        miners = context.miners or []

        if not event_store or not event_store.available:
            context.send_message(
                "⚠️ EventStore no disponible para consultar autopsias.",
                msg_type="AUTOPSY",
                dedup_key=f"cmd_autopsy_{update_id}",
                dbg_cmd="autopsia",
                dbg_update_id=update_id,
            )
            return True

        # Fleet query when no args or "all"
        if not args or args[0].strip().lower() == "all":
            raw_records = event_store.get_latest_autopsy_assessments_fleet(limit=5)
            reports: list[AutopsyReport] = []
            for rec in raw_records:
                try:
                    findings = json.loads(rec.get("findings_json") or "[]")
                    hyps = json.loads(rec.get("hypotheses_json") or "[]")
                    hyp = hyps[0] if hyps else {}
                    reports.append(
                        AutopsyReport(
                            miner_name=rec.get("subject_ref", "Desconocido"),
                            timestamp=float(rec.get("assessment_now_ts", 0.0)),
                            root_cause_category=rec.get("status", "UNRESOLVED"),
                            confidence=hyp.get("confidence", "MEDIUM"),
                            headline=hyp.get("headline", "Reporte Forense"),
                            summary_bullets=tuple(findings),
                            remediation_suggestion=hyp.get("remediation", "Monitorear telemetría."),
                            is_silicon_healthy=bool(hyp.get("is_silicon_healthy", True)),
                            raw_evidence_digest=rec.get("evidence_digest", ""),
                        )
                    )
                except Exception as exc:
                    logger.warning("Error parsing stored autopsy record: %s", exc)

            card = build_fleet_autopsy_summary_card(reports)
            context.send_message(
                card,
                msg_type="AUTOPSY",
                dedup_key=f"cmd_autopsy_{update_id}",
                dbg_cmd="autopsia",
                dbg_update_id=update_id,
            )
            return True

        # Single miner query
        target_miner = resolve_miner(args[0], miners)
        if not target_miner:
            context.send_message(
                "⚠️ Minero no encontrado\nUso: /autopsia [23|24|25|26|all]",
                msg_type="AUTOPSY",
                dedup_key=f"cmd_autopsy_{update_id}",
                dbg_cmd="autopsia",
                dbg_update_id=update_id,
            )
            return True

        miner_name = target_miner.get("name", args[0])
        rec = event_store.get_latest_autopsy_assessment(miner_name)

        if not rec:
            card = (
                f"🔬 AUTOPSIA: {miner_name}\n"
                "──────────────────────────────\n"
                "Sin incidentes recientes.\n"
                "Minero operando nominal.\n"
                "──────────────────────────────"
            )
        else:
            findings = []
            hyp = {}
            try:
                findings = json.loads(rec.get("findings_json") or "[]")
                hyps = json.loads(rec.get("hypotheses_json") or "[]")
                if hyps:
                    hyp = hyps[0]
            except Exception as exc:
                logger.warning("Error parsing assessment json for %s: %s", miner_name, exc)

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
            card = build_autopsy_card(report)

        reply_markup = None
        if rec:
            m_id = str(miner_name).replace("S19JPRO-", "").replace("MINER-", "").replace("MINER_", "")
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "📊 Ver Telemetría", "callback_data": f"chart:{m_id}"},
                        {"text": "🔄 Reiniciar", "callback_data": f"rb_req:{m_id}"},
                    ]
                ]
            }

        context.send_message(
            card,
            msg_type="AUTOPSY",
            dedup_key=f"cmd_autopsy_{update_id}",
            dbg_cmd="autopsia",
            dbg_update_id=update_id,
            reply_markup=reply_markup,
        )
        return True
