"""
chain_collector.py — ASIC Hashboard Chain Telemetry & Predictive Failure Collector (Spec 054, 069, 080, 089).

Decoupled hardware inspection routine extracted from miner_monitor.py.
Collects /api/v1/chains in background, records to SQLite EventStore,
evaluates chain health streaks and predictive failure risks, and dispatches
Telegram diagnostic alerts with dynamic resolution.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from app.core.event_store import EventStore

_logger = logging.getLogger("miner_alerts.hardware.chain_collector")

# In-memory tracking states
_CHAIN_HEALTH_STREAKS: Dict[str, Dict[str, Any]] = {}
_SETTINGS_HEALTH_TIMESTAMPS: Dict[str, float] = {}
_SETTINGS_CORRUPTION_ALERTS: Dict[str, float] = {}


def _log(msg: str) -> None:
    """Dynamic logger delegating to miner_monitor.log if present."""
    try:
        import app.miner_monitor as mm
        log_fn = getattr(mm, "log", None)
        if log_fn:
            log_fn(msg)
            return
    except Exception:
        pass
    _logger.info(msg)


def _send_telegram(
    bot_token: str,
    chat_id: str,
    text: str,
    tag: str = "",
    rate_limit_key: str = "",
    **kwargs: Any,
) -> Any:
    """Dynamic telegram sender delegating to miner_monitor.send_telegram if present."""
    try:
        import app.miner_monitor as mm
        send_fn = getattr(mm, "send_telegram", None)
        if send_fn:
            return send_fn(bot_token, chat_id, text, tag, rate_limit_key, **kwargs)
    except Exception:
        pass
    return None


def _async_collect_chain_telemetry(
    miners_list: list,
    event_store_inst: Optional[Any],
    token: Optional[str] = None,
    miner_name_filter: Optional[str] = None,
    config: Optional[dict] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    states: Optional[Dict[str, Any]] = None,
    state_lock: Optional[threading.Lock] = None,
) -> None:
    """Collect /api/v1/chains in background, record to EventStore, and evaluate predictive health (Spec 054)."""
    if event_store_inst is None or not event_store_inst.available:
        return
    try:
        from app.vnish.chain_collector import fetch_miner_chains
        from app.governance.chain_health import (
            assess_miner_chains,
            evaluate_chain_health_streak,
        )

        for m in miners_list:
            m_name = str(m.get("name", ""))
            if miner_name_filter and m_name != miner_name_filter:
                continue
            m_host = str(m.get("host", ""))
            if not m_host:
                continue
            ok, chains, err = fetch_miner_chains(m_host, token=token, timeout=2.5)
            if ok and chains:
                inserted = event_store_inst.record_chain_samples(m_name, chains)
                _log(f"[CHAIN_TELEMETRY] miner={m_name} collected={len(chains)} inserted={inserted}")

                # Spec 054 T008: Chain Health Assessment & Predictive Alerting
                try:
                    assessment = assess_miner_chains(m_name, chains)
                    streak_data = _CHAIN_HEALTH_STREAKS.setdefault(m_name, {})
                    min_streak = int(config.get("chain_health_min_streak", 2)) if config else 2
                    cooldown = float(config.get("chain_health_cooldown_s", 7200.0)) if config else 7200.0
                    sensor_alerts_enabled = bool(config.get("chain_health_sensor_alerts_enabled", False)) if config else False

                    # Check boot elapsed and warm-up state to suppress transient startup chain alerts
                    _m_st = None
                    if states:
                        if state_lock:
                            with state_lock:
                                for _k, _v in states.items():
                                    if _k.startswith(f"{m_name}|") or getattr(_v, "name", "") == m_name:
                                        _m_st = _v
                                        break
                        else:
                            for _k, _v in states.items():
                                if _k.startswith(f"{m_name}|") or getattr(_v, "name", "") == m_name:
                                    _m_st = _v
                                    break

                    _is_warming = False
                    _elapsed_s = None
                    if _m_st is not None:
                        _now_ts = time.time()
                        _autotune_grace_s = float(config.get("autotune_grace_period_seconds", 900.0)) if config else 900.0
                        _raw_elapsed = getattr(_m_st, "last_elapsed", None)
                        if _raw_elapsed is not None:
                            try:
                                _elapsed_s = float(_raw_elapsed)
                            except (TypeError, ValueError):
                                _elapsed_s = None
                        _reboot_pending = float(getattr(_m_st, "reboot_pending_until", 0.0))
                        _is_warming = (
                            (_elapsed_s is not None and 0 <= _elapsed_s < _autotune_grace_s)
                            or (_reboot_pending > _now_ts)
                        )

                    should_alert, alert_card = evaluate_chain_health_streak(
                        streak_data,
                        assessment,
                        min_streak=min_streak,
                        cooldown_s=cooldown,
                        alert_on_sensor_error=sensor_alerts_enabled,
                        is_warming_up=_is_warming,
                        elapsed_seconds=_elapsed_s,
                    )
                    if (_is_warming or (_elapsed_s is not None and _elapsed_s < 120.0)) and assessment.overall_status in ("CHAIN_FAULT", "CHAIN_SENSOR_ERROR"):
                        _log(f"[CHAIN_HEALTH] Alert suppressed for miner={m_name} during boot/warming_up (status={assessment.overall_status}, elapsed={_elapsed_s}s, warming={_is_warming})")
                    if should_alert and alert_card:
                        if bot_token and chat_id and ((not qa_mode) or qa_notify):
                            _send_telegram(
                                bot_token,
                                str(chat_id),
                                alert_card,
                                "CHAIN_HEALTH",
                                "chain_health_warning",
                            )
                        if event_store_inst and event_store_inst.available:
                            event_store_inst.record_event(
                                occurred_ts=time.time(),
                                miner_key=f"{m_name}|{m_host}",
                                miner_name=m_name,
                                host=m_host,
                                event_type="chain_health_warning",
                                severity="warning",
                                summary=assessment.summary,
                                details={
                                    "overall_status": assessment.overall_status,
                                    "faulty_chains": list(assessment.faulty_chains),
                                    "has_sensor_error": assessment.has_sensor_error,
                                },
                            )
                        _log(f"[CHAIN_HEALTH] Alert sent for miner={m_name} status={assessment.overall_status}")
                except Exception as _ch_exc:
                    _log(f"[CHAIN_HEALTH_ERR] assessment failed for {m_name}: {_ch_exc}")
            elif err:
                _log(f"[CHAIN_TELEMETRY] miner={m_name} host={m_host} error={err}")

            # Spec 080: Firmware Settings Corruption Watchdog (PROP-016)
            try:
                from app.vnish import check_miner_settings_health
                from app.telegram.fleet_cards import build_firmware_corruption_keyboard
                now_ts = time.time()
                last_chk = _SETTINGS_HEALTH_TIMESTAMPS.get(m_name, 0.0)
                if now_ts - last_chk >= 300.0:
                    _SETTINGS_HEALTH_TIMESTAMPS[m_name] = now_ts
                    vnish_pw = str(config.get("vnish_api_password", "admin")) if config else "admin"
                    healthy, issue_code, issue_msg = check_miner_settings_health(m_host, vnish_pw, timeout=2.5)
                    if not healthy and issue_code in ("duplicate_field_error", "config_parse_failure", "http_500_error"):
                        last_alert = _SETTINGS_CORRUPTION_ALERTS.get(m_name, 0.0)
                        if now_ts - last_alert >= 900.0:
                            _SETTINGS_CORRUPTION_ALERTS[m_name] = now_ts
                            short_id = m_name.replace("S19JPRO-", "").replace("s19jpro-", "").replace("S19-", "")
                            _log(f"[FIRMWARE_CORRUPT_ALERT] miner={m_name} host={m_host} code={issue_code} msg={issue_msg}")
                            if bot_token and chat_id and ((not qa_mode) or qa_notify):
                                alert_text = (
                                    f"⚠️ *ALERTA DE FIRMWARE: CONFIGURACIÓN BLOQUEADA*\n\n"
                                    f"• Minero: *{m_name}* (`{m_host}`)\n"
                                    f"• Diagnóstico: `{issue_code}`\n"
                                    f"• Detalle: {issue_msg}\n\n"
                                    f"💡 *Impacto*: El firmware no puede parsear `/config/cgminer.conf`. "
                                    f"El autoswitcher interno está paralizado y no puede subir de potencia ni modular coolers.\n\n"
                                    f"👉 *Acción recomendada*: Solicitar reinicio para reconstituir la configuración limpia desde NAND."
                                )
                                kb = build_firmware_corruption_keyboard(short_id)
                                _send_telegram(
                                    bot_token,
                                    str(chat_id),
                                    alert_text,
                                    "FIRMWARE_CORRUPTION_ALERT",
                                    f"firmware_corrupt_{short_id}",
                                    reply_markup=kb,
                                    is_command=True,
                                raid=False if "raid" not in locals() else None)
                            if event_store_inst and event_store_inst.available:
                                event_store_inst.record_event(
                                    occurred_ts=now_ts,
                                    miner_key=f"{m_name}|{m_host}",
                                    miner_name=m_name,
                                    host=m_host,
                                    event_type="firmware_settings_corrupted",
                                    severity="warning",
                                    summary=f"Configuración de firmware corrupta ({issue_code}): {issue_msg}",
                                    details={"issue_code": issue_code, "issue_msg": issue_msg},
                                )
            except Exception as _fsc_exc:
                _log(f"[FIRMWARE_WATCHDOG_ERR] miner={m_name}: {_fsc_exc}")

            # Spec 081: Pending Preset Restart Status Discovery (PROP-017)
            try:
                from app.vnish import get_miner_status, parse_miner_status_flags
                _st_ok, _st_data, _ = get_miner_status(m_host)
                if _st_ok and _st_data:
                    _, _r_req, _ = parse_miner_status_flags(_st_data)
                    if _r_req:
                        _log(f"[PRESET_WATCHDOG_TELEMETRY] miner={m_name} host={m_host} restart_required=True detectado en telemetria de cadenas")
            except Exception as _pwt_exc:
                _log(f"[PRESET_WATCHDOG_TELEMETRY_ERR] miner={m_name}: {_pwt_exc}")
    except Exception as exc:
        _log(f"[CHAIN_TELEMETRY] worker error: {type(exc).__name__}: {exc}")


def _async_evaluate_predictive_chain_break(
    miners_list: list,
    event_store_inst: Optional[Any],
    miner_states: Dict[str, Any],
    state_lock: threading.Lock,
    config: Optional[dict] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    now_ts: Optional[float] = None,
) -> None:
    """Hourly deep telemetry evaluation & predictive chain break alerting (Spec 069 / PROP-008)."""
    if event_store_inst is None or not event_store_inst.available:
        return
    cfg = config or {}
    if not bool(cfg.get("predictive_chain_break_enabled", True)):
        return

    try:
        from app.governance.chain_health import (
            PredictiveChainEngine,
            PredictiveChainRisk,
            build_predictive_chain_risk_card,
        )

        engine = PredictiveChainEngine()
        now = float(now_ts) if now_ts is not None else time.time()
        cooldown_s = float(cfg.get("chain_warning_cooldown_hours", 24.0)) * 3600.0
        persistence_hours = float(cfg.get("chain_sensor_error_persistence_hours", 12.0))
        since_ts = now - (persistence_hours * 3600.0)

        raw_risks: List[PredictiveChainRisk] = []

        for m in miners_list:
            m_name = str(m.get("name", ""))
            m_host = str(m.get("host", ""))
            if not m_name and not m_host:
                continue

            candidate_keys = [m_name]
            if m_name and m_host:
                candidate_keys.append(f"{m_name}|{m_host}")
            if m_host:
                candidate_keys.append(m_host)

            latest = None
            for ck in candidate_keys:
                latest = event_store_inst.get_latest_chain_samples(ck)
                if latest:
                    break

            chain_ids = [int(r["chain_id"]) for r in latest] if latest else [0, 1, 2]

            chain_samples_map: Dict[int, list] = {}
            for cid in chain_ids:
                samples: list = []
                for ck in candidate_keys:
                    samples = event_store_inst.fetch_chain_samples_window(ck, cid, since_ts)
                    if samples:
                        break
                chain_samples_map[cid] = samples

            for cid in chain_ids:
                c_samples = chain_samples_map.get(cid, [])
                if not c_samples:
                    continue
                sib_map = {sid: s_list for sid, s_list in chain_samples_map.items() if sid != cid}
                risk = engine.evaluate_chain_history(
                    samples=c_samples,
                    now_ts=now,
                    config=cfg,
                    miner_name=m_name,
                    chain_id=cid,
                    sibling_chains_samples=sib_map,
                )
                if risk is not None:
                    raw_risks.append(risk)

        correlated_risks = engine.correlate_electrical_group(
            raw_risks,
            miners_config=miners_list,
            now_ts=now,
        )

        for risk in correlated_risks:
            chain_key = str(risk.chain_id)
            target_miner_name = risk.miner_name

            should_alert = False
            with state_lock:
                st = None
                if target_miner_name.startswith("Grupo "):
                    grp_name = target_miner_name[6:].strip()
                    grp_key = f"group_{grp_name}"
                    member_names = {
                        str(m.get("name")) for m in miners_list
                        if str(m.get("electrical_group") or m.get("group") or m.get("elevator") or "").strip() == grp_name
                    }
                    member_states = [
                        s for k, s in miner_states.items()
                        if any(k == m_nm or k.startswith(f"{m_nm}|") or k.split("|")[0] == m_nm for m_nm in member_names)
                    ]
                    if member_states:
                        last_ts = max(float(s.chain_warnings_ts.get(grp_key, 0.0)) for s in member_states)
                        if (now - last_ts) >= cooldown_s:
                            for s in member_states:
                                s.chain_warnings_ts[grp_key] = now
                            should_alert = True
                    else:
                        should_alert = True
                else:
                    for k, s in miner_states.items():
                        if (
                            k == target_miner_name
                            or k.startswith(f"{target_miner_name}|")
                            or k.split("|")[0] == target_miner_name
                        ):
                            st = s
                            break

                    if st is not None:
                        last_ts = float(st.chain_warnings_ts.get(chain_key, 0.0))
                        if (now - last_ts) >= cooldown_s:
                            st.chain_warnings_ts[chain_key] = now
                            should_alert = True
                    else:
                        should_alert = True

            if should_alert:
                alert_card = build_predictive_chain_risk_card(risk)
                if bot_token and chat_id and ((not qa_mode) or qa_notify):
                    _send_telegram(
                        bot_token,
                        str(chat_id),
                        alert_card,
                        "CHAIN_PREDICTIVE",
                        "predictive_chain_break_warning",
                    )
                if event_store_inst and event_store_inst.available:
                    event_store_inst.record_event(
                        occurred_ts=now,
                        miner_key=risk.miner_name,
                        miner_name=risk.miner_name,
                        host="",
                        event_type="predictive_chain_break_warning",
                        severity=risk.severity.lower(),
                        summary=risk.message,
                        details={
                            "risk_type": risk.risk_type,
                            "chain_id": risk.chain_id,
                            "persistence_hours": risk.persistence_hours,
                            "error_sample_pct": risk.error_sample_pct,
                            "faulty_locs": list(risk.faulty_locs),
                        },
                    )
                _log(f"[PREDICTIVE_CHAIN] Alert sent for miner={risk.miner_name} chain={risk.chain_id} risk={risk.risk_type}")

    except Exception as exc:
        _log(f"[PREDICTIVE_CHAIN_ERR] worker failed: {type(exc).__name__}: {exc}")
