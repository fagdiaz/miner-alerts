from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RestartClassification:
    classification: str
    severity: str
    restart_reason: str
    action_source: Optional[str]
    action_ts: Optional[float]
    action_age_seconds: Optional[float]


def classify_restart(
    *,
    restart_reason: str,
    detected_ts: float,
    last_manual_action_ts: Optional[float],
    last_auto_action_ts: Optional[float],
    last_preset_change_ts: Optional[float] = None,
    last_shutdown_ts: Optional[float] = None,
    attribution_window_seconds: int,
    skew_tolerance_seconds: int = 10,
) -> RestartClassification:
    candidates: list[tuple[float, str]] = []
    for action_source, action_ts in (
        ("manual", last_manual_action_ts),
        ("auto", last_auto_action_ts),
        ("preset", last_preset_change_ts),
        ("shutdown", last_shutdown_ts),
    ):
        if action_ts is None:
            continue
        action_value = float(action_ts)
        if action_value > detected_ts + skew_tolerance_seconds:
            continue
        action_age = max(0.0, detected_ts - action_value)
        if action_age <= attribution_window_seconds:
            candidates.append((action_value, action_source))

    if not candidates:
        return RestartClassification(
            classification="unexpected",
            severity="critical",
            restart_reason=restart_reason,
            action_source=None,
            action_ts=None,
            action_age_seconds=None,
        )

    action_ts, action_source = max(candidates, key=lambda item: item[0])
    return RestartClassification(
        classification=f"expected_{action_source}",
        severity="info",
        restart_reason=restart_reason,
        action_source=action_source,
        action_ts=action_ts,
        action_age_seconds=max(0.0, detected_ts - action_ts),
    )


def evaluate_auto_restart_candidate(
    *,
    now_ts: float,
    responded: bool,
    rate_ths: Optional[float],
    threshold_ths: float,
    active_boards: Optional[int],
    expected_boards: int,
    miner_state: str,
    restart_required: bool,
    reboot_required: bool,
    auto_restart_enabled: bool,
    last_auto_restart_ts: Optional[float],
    auto_restart_cooldown_seconds: float,
    auto_restart_count: int,
    max_retries_before_reboot: int,
    in_maintenance: bool = False,
    is_snoozed: bool = False,
    gov: Optional[Any] = None,
    elapsed: Optional[int] = None,
    min_elapsed_seconds: int = 180,
    startup_grace_active: bool = False,
) -> Tuple[bool, Optional[str], Optional[float]]:
    """Evaluates whether a miner qualifies for a Soft Auto-Restart of mining (Level 1).

    Returns: (is_candidate: bool, reason_or_blocker: Optional[str], cooldown_remaining: Optional[float])
    """
    if not auto_restart_enabled:
        return False, "disabled", None

    if startup_grace_active:
        return False, "startup_grace_active", None

    # Spec 057: Intervention Governance Guard
    from app.governance.intervention_policy import ACTION_REBOOT_L1, should_allow_intervention
    from app.governance._orchestrator_state import get_intervention_gov

    gov_check = gov if gov is not None else get_intervention_gov()
    if gov_check is not None:
        allowed, reason = should_allow_intervention(ACTION_REBOOT_L1, gov_check, now_ts)
        if not allowed:
            return False, f"interventions_blocked:{reason}", None

    if not responded:
        return False, "unresponsive", None
    if in_maintenance or is_snoozed:
        return False, "maintenance_or_snoozed", None
    if reboot_required:
        return False, "hardware_reboot_required", None

    # Individual Miner Warmup Guard: give miner at least min_elapsed_seconds post-boot
    if elapsed is not None and elapsed < min_elapsed_seconds:
        return False, "miner_warming_up", None

    norm_state = (miner_state or "").strip().lower()
    if norm_state in (
        "starting",
        "init",
        "initializing",
        "benchmarking",
        "rebooting",
        "booting",
        "tuning",
        "warmup",
        "warming_up",
    ):
        return False, "transient_starting", None

    # Check degradation triggers
    is_stopped = norm_state in ("stopped", "paused", "idle", "stop", "halted")
    is_zero_hash = (rate_ths is not None and rate_ths <= 0.0)
    is_zero_boards = (active_boards is not None and active_boards <= 0)
    has_restart_flag = bool(restart_required)

    if not (is_stopped or is_zero_hash or is_zero_boards or has_restart_flag):
        return False, "not_needed", None

    # Check retry limit before escalating to hardware reboot
    if auto_restart_count >= max_retries_before_reboot:
        return False, "max_retries_exceeded", None

    # Check cooldown
    if last_auto_restart_ts is not None:
        delta = max(0.0, now_ts - last_auto_restart_ts)
        if delta < auto_restart_cooldown_seconds:
            return False, "cooldown", auto_restart_cooldown_seconds - delta

    trigger_reason = "restart_required_flag" if has_restart_flag else (
        "stopped_state" if is_stopped else (
            "zero_boards" if is_zero_boards else "zero_hashrate"
        )
    )
    return True, trigger_reason, None


def evaluate_preset_restart_candidate(
    now_ts: float,
    vnish_restart_required: bool,
    is_hash_degraded: bool,
    is_warming_up: bool,
    max_chip_temp_c: Optional[float],
    detected_ts: Optional[float],
    last_restart_ts: Optional[float],
    soak_window_seconds: float = 300.0,
    cooldown_seconds: float = 180.0,
    max_safe_temp_c: float = 80.0,
    thermal_pause_active: bool = False,
) -> Tuple[bool, str]:
    """Pure decision function for Spec 081 Watchdog."""
    if not vnish_restart_required:
        return False, "restart_not_required"
    if is_hash_degraded:
        return False, "handled_by_degraded_auto_restart"
    if thermal_pause_active:
        return False, "thermal_pause_active"
    if is_warming_up:
        return False, "warming_up"
    if max_chip_temp_c is not None and max_chip_temp_c >= max_safe_temp_c:
        return False, f"chip_temp_too_high_{max_chip_temp_c:.1f}C"
    if detected_ts is not None and (now_ts - detected_ts) < soak_window_seconds:
        rem = soak_window_seconds - (now_ts - detected_ts)
        return False, f"soak_window_active_{rem:.0f}s"
    if last_restart_ts is not None and (now_ts - last_restart_ts) < cooldown_seconds:
        rem = cooldown_seconds - (now_ts - last_restart_ts)
        return False, f"cooldown_active_{rem:.0f}s"
    return True, "ready_for_preset_restart"


def _async_execute_mining_restart(
    host: str,
    password: str,
    miner_name: str,
    miner_dict: dict,
    trigger_reason: str,
    attempt: int,
    max_attempts: int,
    bot_token: str,
    chat_id: str,
    qa_mode: bool,
    qa_notify: bool,
    event_store: Any,
    pre_clamp_preset: str = "1800",
) -> None:
    """Asynchronously execute soft mining restart with APW12 pre-clamp protection."""
    import logging
    import time
    from app.telegram.fleet_cards import display_name
    import sys
    from app.vnish.client import safe_restart_mining, safe_set_miner_preset
    from app.telegram.sender import send_telegram

    mm = sys.modules.get("app.miner_monitor")
    _safe_set_preset = getattr(mm, "safe_set_miner_preset", safe_set_miner_preset) if mm else safe_set_miner_preset
    _safe_restart = getattr(mm, "safe_restart_mining", safe_restart_mining) if mm else safe_restart_mining
    _send_tg = getattr(mm, "send_telegram", send_telegram) if mm else send_telegram
    from app.core.pipeline import record_action_outcome
    _rec_outcome = getattr(mm, "record_action_outcome", record_action_outcome) if mm else record_action_outcome

    logger = logging.getLogger("miner-alerts")
    try:
        ts = time.time()
        disp_name = display_name(miner_name)
        logger.info(
            "[AUTO-RESTART] %s (%s) iniciando soft restart de minado (intento %d/%d, razon=%s)...",
            disp_name, host, attempt, max_attempts, trigger_reason,
        )

        from app.governance.intervention_policy import ACTION_PRESET_BALANCER, should_allow_intervention
        from app.governance._orchestrator_state import get_intervention_gov

        gov_obj = get_intervention_gov()
        presets_allowed = True
        if gov_obj is not None:
            allowed, _ = should_allow_intervention(ACTION_PRESET_BALANCER, gov_obj, ts)
            presets_allowed = allowed

        if presets_allowed and pre_clamp_preset:
            logger.info(
                "[SAFE-RECOVERY] %s (%s) aplicando pre-clamp defensivo a %sW para proteger fuente APW12...",
                disp_name, host, pre_clamp_preset,
            )
            _pre_hw_max = miner_dict.get("max_hardware_preset", "2700W").rstrip("W") if isinstance(miner_dict, dict) else "2700"
            clamp_ok, clamp_err = _safe_set_preset(host, password, pre_clamp_preset, clamp_top_preset=False, top_preset=_pre_hw_max)
            if clamp_ok:
                logger.info(
                    "[SAFE-RECOVERY] %s (%s) pre-clamp a %sW aplicado con exito. Asentando voltajes (2.0s)...",
                    disp_name, host, pre_clamp_preset,
                )
                time.sleep(2.0)
            else:
                logger.warning(
                    "[WARN] [SAFE-RECOVERY] %s (%s) no se pudo aplicar pre-clamp (%s); procediendo con soft restart directo.",
                    disp_name, host, clamp_err,
                )
        else:
            logger.info(
                "[SAFE-RECOVERY] %s (%s) pre-clamp suprimido por gobernanza; procediendo con soft restart directo.",
                disp_name, host,
            )

        ok, err = _safe_restart(host, password)
        if ok:
            logger.info(
                "[AUTO-RESTART] %s (%s) soft mining restart enviado exitosamente (intento %d/%d).",
                disp_name, host, attempt, max_attempts,
            )
            if (not qa_mode) or qa_notify:
                _send_tg(
                    bot_token,
                    str(chat_id),
                    f"[AUTO-RESTART] {disp_name} hasheo detenido ({trigger_reason}) -> reinicio rapido de minado enviado (Nivel 1, intento {attempt}/{max_attempts})\n"
                    f"Diagnostico: /why",
                    "REBOOT",
                    "auto_restart",
                )
            _rec_outcome(
                event_store,
                occurred_ts=ts,
                miner=miner_dict,
                action="restart_mining",
                source="auto",
                ok=True,
                message=f"Soft restart sent ({trigger_reason})",
            )
        else:
            logger.warning("[WARN] [AUTO-RESTART] %s (%s) fallo soft restart de minado: %s", disp_name, host, err)
            if (not qa_mode) or qa_notify:
                _send_tg(
                    bot_token,
                    str(chat_id),
                    f"[AUTO-RESTART FAILED] {disp_name}: fallo al reiniciar minado: {err}\n"
                    f"Diagnostico: /why",
                    "ERROR",
                    "auto_restart_failed",
                )
            _rec_outcome(
                event_store,
                occurred_ts=ts,
                miner=miner_dict,
                action="restart_mining",
                source="auto",
                ok=False,
                message=str(err),
            )
    except Exception as _exc:
        logger.warning(
            "[WARN] [AUTO-RESTART] %s excepcion no esperada en hilo AutoRestart: %s: %s",
            miner_name, type(_exc).__name__, _exc,
        )


def _async_execute_preset_restart(
    host: str,
    password: str,
    miner_name: str,
    miner_dict: dict,
    target_preset: str,
    bot_token: str,
    chat_id: str,
    qa_mode: bool,
    qa_notify: bool,
    event_store: Any,
) -> None:
    """Execute soft mining restart to apply a pending Vnish preset (Spec 081 / PROP-017)."""
    import logging
    import time
    from app.telegram.fleet_cards import display_name
    from app.vnish.client import safe_restart_mining

    logger = logging.getLogger("miner-alerts")
    try:
        ts = time.time()
        disp_name = display_name(miner_name)
        logger.info(
            "[PRESET-WATCHDOG] %s (%s) ejecutando soft restart para aplicar preset pendiente (%s)...",
            disp_name, host, target_preset,
        )
        ok, err = safe_restart_mining(host, password)
        if ok:
            logger.info(
                "[PRESET-WATCHDOG] %s (%s) soft mining restart exitoso. Preset %s activado.",
                disp_name, host, target_preset,
            )
            if (not qa_mode) or qa_notify:
                from app.telegram.sender import send_telegram
                msg = (
                    f"🔄 *PRESET APLICADO*\n\n"
                    f"• Minero: *{disp_name}*\n"
                    f"• Target: *{target_preset}*\n"
                    f"• Razón: Watchdog de preset\n\n"
                    f"Reinicio suave ejecutado\n"
                    f"para aplicar configuración."
                )
                send_telegram(
                    bot_token,
                    str(chat_id),
                    msg,
                    "PRESET_WATCHDOG",
                    f"preset_restart_{miner_name}",
                    is_command=True,
                )
            from app.miner_monitor import record_action_outcome
            record_action_outcome(
                event_store,
                occurred_ts=ts,
                miner=miner_dict,
                action="preset_restart_applied",
                source="auto",
                ok=True,
                message=f"Preset restart applied ({target_preset})",
            )
            if event_store and getattr(event_store, "available", False):
                try:
                    event_store.record_event(
                        occurred_ts=ts,
                        miner_key=f"{miner_name}|{host}",
                        miner_name=miner_name,
                        host=host,
                        event_type="preset_restart_applied",
                        severity="info",
                        summary=f"Reinicio suave de minado aplicado para activar preset {target_preset}",
                        details={"target_preset": target_preset},
                    )
                except Exception:
                    pass
        else:
            logger.warning("[WARN] [PRESET-WATCHDOG] %s (%s) fallo al ejecutar soft restart: %s", disp_name, host, err)
            from app.miner_monitor import record_action_outcome
            record_action_outcome(
                event_store,
                occurred_ts=ts,
                miner=miner_dict,
                action="preset_restart_applied",
                source="auto",
                ok=False,
                message=str(err),
            )
    except Exception as _exc:
        logger.warning(
            "[PRESET-WATCHDOG] %s excepcion en hilo PresetRestart: %s: %s",
            miner_name, type(_exc).__name__, _exc,
        )
