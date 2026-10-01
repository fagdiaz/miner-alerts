"""
app/governance/governance_context.py
Spec 082 — MinerGovernanceContext: Contrato de Estado Centralizado (PROP-018)

Dataclass inmutable que actúa como fuente de verdad compartida entre todos los
subsistemas de gobernanza (Fan Governor, Elevator Budget, FGA, Watchdogs).
Elimina la visibilidad parcial que causó el nudo S19JPRO-24 (Fricciones F-01/F-02).

Diseño:
- frozen=True: immutabilidad garantizada post-construcción.
- from_state(): classmethod puro sin I/O ni efectos secundarios.
- Campos opcionales (Optional[X]): valor None = dato no disponible → comportamiento conservador.
- Sin dependencias en miner_monitor.py (evita importaciones circulares).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional


@dataclass(frozen=True)
class MinerGovernanceContext:
    """
    Snapshot inmutable del estado de gobernanza de un minero en un instante de ciclo.

    Consumido por todos los subsistemas de gobernanza como fuente de verdad única.
    Se construye una vez por ciclo por minero en miner_monitor.py y se pasa por
    referencia a compute_governor_step(), evaluate_facility_transition_permission(), etc.

    Dominios:
        Potencia  : potencia real ejecutada vs configurada, preset discrepancia.
        Térmico   : temperatura de chips/inlet, R_th de silicio, cohorte FGA.
        Firmware  : restart_required, thermal_pause, lockout.
        Operativo : uptime, grupo eléctrico, nombre, fase de arranque.
    """

    # ── Dominio Potencia ──────────────────────────────────────────────────────
    current_power_w: Optional[float] = None
    """Potencia real medida en las cadenas (W) — cgminer ejecutando actualmente."""

    target_power_w: Optional[float] = None
    """Potencia objetivo del ciclo de gobernanza (W)."""

    configured_preset: Optional[str] = None
    """Preset escrito en /config/cgminer.conf por VNish (p. ej. '2700')."""

    executed_preset: Optional[str] = None
    """Preset activo en el proceso cgminer (puede diferir de configured_preset)."""

    # ── Dominio Térmico ───────────────────────────────────────────────────────
    chip_temp_c: Optional[float] = None
    """Temperatura máxima de chips (°C) — max(cadenas)."""

    inlet_temp_c: Optional[float] = None
    """Temperatura del aire de entrada al gabinete (°C)."""

    fga_thermal_resistance: Optional[float] = None
    """R_th = (T_chip - T_inlet) / P — resistencia térmica de silicio del FGA."""

    fga_cohort: Optional[str] = None
    """Clasificación FGA: 'COOL' | 'STANDARD' | 'HOT' | None si no disponible."""

    # ── Dominio Estado Firmware ───────────────────────────────────────────────
    restart_required: bool = False
    """
    VNish preset_required: cgminer corre con preset antiguo, necesita restart
    para aplicar el preset escrito en /config/cgminer.conf.
    Cuando True + current_power_w >= 500W → Fan Governor usa current_power_w
    como target efectivo (elimina trampa ACTION_RECOVERY_MAX_COOLING).
    """

    restart_detected_ts: Optional[float] = None
    """Timestamp (unix) de la primera detección de restart_required=True."""

    thermal_pause_active: bool = False
    """True si hay una pausa térmica activa (thermal_pause_until_ts > now_ts)."""

    thermal_lockout_active: bool = False
    """True si hay un lockout de hardware activo (thermal_lockout_until_ts > now_ts)."""

    # ── Dominio Operativo ─────────────────────────────────────────────────────
    uptime_seconds: Optional[float] = None
    """Uptime del minero en segundos (last_elapsed si disponible)."""

    electrical_group: Optional[str] = None
    """Grupo eléctrico del minero ('elevator_1' | 'elevator_2' | None)."""

    miner_name: str = ""
    """Nombre display del minero (p. ej. 'S19JPRO-24')."""

    is_warming_up: bool = False
    """True si el minero está en fase de cold-boot grace (autotune_grace_period)."""

    # ── Dominio Fan Governor & Telemetría Aditiva (Spec 084) ──────────────────
    fan_duty: Optional[int] = None
    """Duty actual del Fan Governor (0-100%)."""

    fan_action: Optional[str] = None
    """Última acción emitida por el Fan Governor."""

    recovery_since_ts: Optional[float] = None
    """Timestamp unix de inicio de episodio ACTION_RECOVERY_MAX_COOLING."""

    is_stock_firmware: bool = False
    """True si el minero corre firmware stock Antminer."""

    # ── Timestamp de construcción ─────────────────────────────────────────────
    built_at_ts: float = field(default_factory=time.monotonic)
    """Monotonic timestamp de construcción del contexto (para latencia de auditoría)."""

    # ─────────────────────────────────────────────────────────────────────────
    # Propiedades calculadas (compatibles con frozen dataclass)
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def max_chip_temp_c(self) -> Optional[float]:
        """Alias para chip_temp_c por compatibilidad retroactiva."""
        return self.chip_temp_c

    @property
    def effective_target_power_w(self) -> Optional[float]:
        """
        Potencia objetivo efectiva para el Fan Governor.

        Cuando restart_required=True y current_power_w >= 500W, el minero está
        corriendo con un preset antiguo (cgminer no ha aplicado el nuevo preset
        todavía). En ese caso, la potencia *real ejecutada* (current_power_w) es
        la referencia correcta para el lazo de control, NO el target configurado.

        Usar target_power_w en ese estado genera una brecha ficticia que dispara
        ACTION_RECOVERY_MAX_COOLING de forma incorrecta (bug F-01 / S19JPRO-24).

        Returns:
            - current_power_w si restart_required=True y current_power_w >= 500W
            - target_power_w en todos los demás casos (None si no está disponible)
        """
        if (
            self.restart_required
            and self.current_power_w is not None
            and self.current_power_w >= 500.0
        ):
            return self.current_power_w
        return self.target_power_w

    # ─────────────────────────────────────────────────────────────────────────
    # Factory method
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_state(
        cls,
        state: Any,
        now_ts: float,
        miner_config: Dict[str, Any],
    ) -> "MinerGovernanceContext":
        """
        Construye un MinerGovernanceContext desde un MinerState y configuración.

        Función pura: sin I/O, sin efectos secundarios, sin mutación de estado.
        Todos los accesos a state usan getattr con valor por defecto seguro.

        Args:
            state:         MinerState del minero (o cualquier objeto con getattr).
            now_ts:        Timestamp unix actual (para evaluar is_warming_up, pauses).
            miner_config:  Dict de configuración del minero (contiene electrical_group, etc.)

        Returns:
            MinerGovernanceContext inmutable.
        """
        # Dominio Potencia
        current_power_w: Optional[float] = getattr(state, "last_power_w", None)
        if current_power_w is None:
            current_power_w = getattr(state, "governor_last_power_w", None)

        target_power_w: Optional[float] = (
            miner_config.get("target_power_w")
            or getattr(state, "vnish_discovered_target_power_w", None)
        )
        configured_preset: Optional[str] = (
            getattr(state, "vnish_discovered_preset", None)
            or getattr(state, "balancer_preset", None)
        )
        executed_preset: Optional[str] = getattr(state, "vnish_discovered_preset", None)
        # Nota: configured_preset y executed_preset difieren cuando restart_required=True.
        # miner_monitor.py puede pasar executed_preset distinto si tiene esa info.

        # Dominio Térmico
        chip_temp_c: Optional[float] = (
            getattr(state, "last_max_chip_temp", None)
            or getattr(state, "governor_last_temp_c", None)
            or getattr(state, "last_temp_c", None)
        )
        inlet_temp_c: Optional[float] = getattr(state, "inlet_temp_c", None)
        fga_thermal_resistance: Optional[float] = getattr(state, "fga_thermal_resistance", None)
        fga_cohort: Optional[str] = getattr(state, "fga_cohort", None)

        # Dominio Fan Governor & Telemetría Aditiva (Spec 084)
        fan_duty: Optional[int] = getattr(state, "governor_duty", None)
        fan_action: Optional[str] = getattr(state, "governor_last_action", None)
        recovery_since_ts: Optional[float] = getattr(state, "governor_recovery_since_ts", None)
        is_stock_firmware: bool = bool(getattr(state, "is_stock_firmware", False))

        # Dominio Estado Firmware
        restart_required: bool = bool(getattr(state, "vnish_restart_required", False))
        restart_detected_ts: Optional[float] = getattr(state, "vnish_restart_detected_ts", None)

        _thermal_pause_until: Optional[float] = getattr(state, "thermal_pause_until_ts", None)
        thermal_pause_active: bool = (
            _thermal_pause_until is not None and now_ts < _thermal_pause_until
        )

        _thermal_lockout_until: Optional[float] = getattr(state, "thermal_lockout_until_ts", None)
        thermal_lockout_active: bool = (
            _thermal_lockout_until is not None and now_ts < _thermal_lockout_until
        )

        # Dominio Operativo
        uptime_seconds: Optional[float] = getattr(state, "last_elapsed", None)
        if uptime_seconds is not None:
            uptime_seconds = float(uptime_seconds)

        electrical_group: Optional[str] = (
            miner_config.get("electrical_group")
            or miner_config.get("group")
            or None
        )
        miner_name: str = str(
            miner_config.get("name", "") or miner_config.get("display_name", "") or ""
        )

        # is_warming_up: basado en elapsed y autotune_grace_period
        _autotune_grace_s = float(miner_config.get("autotune_grace_period_seconds", 900.0))
        _reboot_pending_until: float = float(getattr(state, "reboot_pending_until", 0.0))
        is_warming_up: bool = (
            (uptime_seconds is not None and 0 <= uptime_seconds < _autotune_grace_s)
            or (_reboot_pending_until > now_ts)
        )

        return cls(
            current_power_w=current_power_w,
            target_power_w=target_power_w,
            configured_preset=configured_preset,
            executed_preset=executed_preset,
            chip_temp_c=chip_temp_c,
            inlet_temp_c=inlet_temp_c,
            fga_thermal_resistance=fga_thermal_resistance,
            fga_cohort=fga_cohort,
            restart_required=restart_required,
            restart_detected_ts=restart_detected_ts,
            thermal_pause_active=thermal_pause_active,
            thermal_lockout_active=thermal_lockout_active,
            uptime_seconds=uptime_seconds,
            electrical_group=electrical_group,
            miner_name=miner_name,
            is_warming_up=is_warming_up,
            fan_duty=fan_duty,
            fan_action=fan_action,
            recovery_since_ts=recovery_since_ts,
            is_stock_firmware=is_stock_firmware,
            built_at_ts=time.monotonic(),
        )
