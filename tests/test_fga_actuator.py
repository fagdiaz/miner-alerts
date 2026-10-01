"""
Unit and Contract tests for FGA Actuator Loop (Spec 083 / PROP-019).
"""

import os
import tempfile
import time
import unittest
from datetime import datetime, time as dtime

from app.core.event_store import EventStore
from app.governance.elevator_budget import (
    ACTION_ALLOW_TRANSITION,
    ACTION_HOLD_FACILITY_SETTLE,
    ACTION_HOLD_HARDWARE_LIMIT,
    ACTION_HOLD_INCIDENT_QUIET,
    ACTION_HOLD_THERMAL_HEADROOM,
    FacilityBudgetState,
)
from app.governance.facility_agent import (
    STRATEGY_BALANCED,
    STRATEGY_MAX_POWER,
    build_thermal_profile,
    evaluate_asymmetric_allocation,
)
from app.governance.fga_actuator import (
    FgaActuatorDecision,
    evaluate_fga_actuator_step,
    execute_fga_actuator_step,
)
from app.governance.governance_context import MinerGovernanceContext


class TestFgaEventStorePersistence(unittest.TestCase):
    """T4.2: Verifica la tabla facility_agent_actions y métodos de EventStore."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_events.db")
        self.store = EventStore(self.db_path)
        self.assertTrue(self.store.available)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_record_and_get_facility_agent_action(self):
        now_ts = time.time()
        ok = self.store.record_facility_agent_action(
            miner_name="S19JPRO-26",
            electrical_group="elevator_2",
            strategy="balanced",
            from_preset="2500W",
            to_preset="2700W",
            action_status="EXECUTED",
            gate_name="ALLOW_TRANSITION",
            reason="Silicio frío verificado; compuertas superadas",
            power_w=2700.0,
            chip_temp_c=74.5,
            thermal_resistance=0.0185,
            created_ts=now_ts,
        )
        self.assertTrue(ok)

        # Recuperar acciones globales
        actions = self.store.get_facility_agent_actions(limit=10)
        self.assertEqual(len(actions), 1)
        act = actions[0]
        self.assertEqual(act["miner_name"], "S19JPRO-26")
        self.assertEqual(act["electrical_group"], "elevator_2")
        self.assertEqual(act["from_preset"], "2500W")
        self.assertEqual(act["to_preset"], "2700W")
        self.assertEqual(act["action_status"], "EXECUTED")
        self.assertEqual(act["gate_name"], "ALLOW_TRANSITION")
        self.assertAlmostEqual(act["thermal_resistance"], 0.0185, places=4)

        # Filtrado por nombre de minero
        self.assertEqual(len(self.store.get_facility_agent_actions(miner_name="S19JPRO-26")), 1)
        self.assertEqual(len(self.store.get_facility_agent_actions(miner_name="S19JPRO-23")), 0)


class TestFgaTelemetryHarmonization(unittest.TestCase):
    """T4.3: Verificación de F-04: R_th usa potencia real cuando restart_required=True."""

    def test_rth_uses_real_power_when_restart_required_true(self):
        # Contexto donde el minero tiene target 2700W configurado pero opera a 2490W reales
        # con restart_required=True (escenario exacto de S19JPRO-24)
        ctx = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2490.0,
            target_power_w=2700.0,
            configured_preset="2700",
            executed_preset="2500",
            chip_temp_c=74.0,
            inlet_temp_c=25.0,
            restart_required=True,
            electrical_group="elevator_1",
        )

        prof = build_thermal_profile("S19JPRO-24", ctx=ctx)
        # delta_t = 74.0 - 25.0 = 49.0°C
        # R_th debe ser calculado sobre 2490W (potencia real), NO 2700W!
        # 49.0 / 2490.0 = 0.01968 °C/W (COOL)
        # Si hubiera usado 2700W: 49.0 / 2700.0 = 0.01815 °C/W (distorsión artificial)
        expected_r_th = round(49.0 / 2490.0, 5)
        self.assertAlmostEqual(prof.thermal_resistance, expected_r_th, places=4)
        self.assertEqual(prof.current_power_w, 2490.0)


class TestFgaActuatorCycle(unittest.TestCase):
    """T4.4, T4.5, T4.6: Pruebas del ciclo evaluador y compuertas del ElevatorBudget."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_events.db")
        self.store = EventStore(self.db_path)
        self.facility_state = FacilityBudgetState()
        # Viernes 14:00 hs (fuera de ventana pico 08:30-10:30 y 19:30-22:30, pero dentro de horario solar 11:00-17:00)
        # Usamos 23:00 hs para horario valle sin restricciones solares
        self.valle_dt = datetime(2026, 10, 2, 23, 0, 0)
        self.valle_ts = 1790900000.0

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_evaluate_step_allows_transition_when_all_gates_pass(self):
        """T4.4: Minero frío puede subir a 2700W en horario valle con partner a 2500W."""
        ctx_m23 = MinerGovernanceContext(
            miner_name="S19JPRO-23",
            current_power_w=2500.0,
            configured_preset="2500",
            executed_preset="2500",
            chip_temp_c=78.0,
            inlet_temp_c=25.0,
            electrical_group="elevator_1",
        )
        # M24 es un silicio frío excepcional (T_chip=68°C, inlet=25°C -> R_th=0.0172 -> COOL)
        ctx_m24 = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            executed_preset="2500",
            chip_temp_c=68.0,
            inlet_temp_c=25.0,
            electrical_group="elevator_1",
        )

        decision = evaluate_fga_actuator_step(
            governance_contexts=[ctx_m23, ctx_m24],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
            strategy=STRATEGY_BALANCED,
            presets_enabled=True,
        )

        self.assertTrue(decision.can_proceed)
        self.assertEqual(decision.candidate_miner, "S19JPRO-24")
        self.assertEqual(decision.target_preset, "2700W")
        self.assertEqual(decision.gate_action, ACTION_ALLOW_TRANSITION)
        self.assertEqual(decision.action_status, "PERMITTED")

    def test_execute_step_simulated_in_qa_mode(self):
        """T4.4 & T4.8: Ejecución simulada cuando qa_mode=True."""
        ctx_m23 = MinerGovernanceContext(
            miner_name="S19JPRO-23",
            current_power_w=2500.0,
            configured_preset="2500",
            executed_preset="2500",
            chip_temp_c=78.0,
            electrical_group="elevator_1",
        )
        ctx_m24 = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            executed_preset="2500",
            chip_temp_c=68.0,
            electrical_group="elevator_1",
        )

        decision = evaluate_fga_actuator_step(
            governance_contexts=[ctx_m23, ctx_m24],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
            strategy=STRATEGY_BALANCED,
        )

        executed_dec = execute_fga_actuator_step(
            decision=decision,
            host="192.168.1.124",
            password="admin",
            facility_state=self.facility_state,
            now_ts=self.valle_ts,
            qa_mode=True,
            event_store=self.store,
        )

        self.assertEqual(executed_dec.action_status, "SIMULATED")
        # Verificar que se registró la transición en facility_state
        in_settle, rem, _ = self.facility_state.is_facility_in_settle(self.valle_ts + 10.0)
        self.assertTrue(in_settle)
        self.assertAlmostEqual(rem, 170.0, delta=1.0)

        # Verificar que se persistió en EventStore
        acts = self.store.get_facility_agent_actions(miner_name="S19JPRO-24")
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["action_status"], "SIMULATED")

    def test_blocked_by_facility_settle_window(self):
        """T4.5: Gate 1 bloquea si hubo un cambio de preset hace menos de 180s."""
        self.facility_state.record_transition("S19JPRO-23", "2500W", self.valle_ts - 60.0)

        ctx_m23 = MinerGovernanceContext(
            miner_name="S19JPRO-23",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=78.0,
            electrical_group="elevator_1",
        )
        ctx_m24 = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=68.0,
            electrical_group="elevator_1",
        )

        decision = evaluate_fga_actuator_step(
            governance_contexts=[ctx_m23, ctx_m24],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
        )

        self.assertFalse(decision.can_proceed)
        self.assertEqual(decision.gate_action, ACTION_HOLD_FACILITY_SETTLE)
        self.assertEqual(decision.action_status, "BLOCKED")
        self.assertGreater(decision.remaining_settle_s, 0.0)

    def test_blocked_by_incident_quiet_window(self):
        """T4.5: Gate 0 bloquea si el elevador está en reposo post-incidente (300s)."""
        self.facility_state.record_group_incident("elevator_1", self.valle_ts - 100.0)

        ctx_m23 = MinerGovernanceContext(
            miner_name="S19JPRO-23",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=78.0,
            electrical_group="elevator_1",
        )
        ctx_m24 = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=68.0,
            electrical_group="elevator_1",
        )

        decision = evaluate_fga_actuator_step(
            governance_contexts=[ctx_m23, ctx_m24],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
        )

        self.assertFalse(decision.can_proceed)
        self.assertEqual(decision.gate_action, ACTION_HOLD_INCIDENT_QUIET)
        self.assertEqual(decision.action_status, "BLOCKED")

    def test_blocked_by_hardware_ceiling(self):
        """T4.6: Gate 2 respeta el techo de hardware de silicio individual (p.ej. M25 a 2500W)."""
        # Configuramos S19JPRO-25 con límite de hardware en 2500W
        config = {
            "miner_hardware_limits": {
                "S19JPRO-25": "2500W"
            }
        }
        ctx_m25 = MinerGovernanceContext(
            miner_name="S19JPRO-25",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=67.0,  # Muy frío, querría subir a 2700W
            inlet_temp_c=25.0,
            electrical_group="elevator_2",
        )
        ctx_m26 = MinerGovernanceContext(
            miner_name="S19JPRO-26",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=75.0,
            electrical_group="elevator_2",
        )

        decision = evaluate_fga_actuator_step(
            governance_contexts=[ctx_m25, ctx_m26],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
            config=config,
        )

        self.assertFalse(decision.can_proceed)
        self.assertEqual(decision.gate_action, ACTION_HOLD_HARDWARE_LIMIT)
        self.assertEqual(decision.action_status, "BLOCKED")

    def test_blocked_by_thermal_headroom(self):
        """T4.6: Gate 3.1 exige T_chip < 80.0°C antes de autorizar 2700W."""
        ctx_m23 = MinerGovernanceContext(
            miner_name="S19JPRO-23",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=78.0,
            electrical_group="elevator_1",
        )
        # M24 clasifica con R_th frío (inlet 20°C, P=2500, R_th=0.018 -> pred 2700 = 68.6°C <= 82.5°C)
        # pero el chip actualmente está en 80.5°C (por encima de valley_step_up_max_chip_temp_c 80.0°C)
        ctx_m24 = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=80.5,
            inlet_temp_c=20.0,
            fga_thermal_resistance=0.018,
            electrical_group="elevator_1",
        )

        decision = evaluate_fga_actuator_step(
            governance_contexts=[ctx_m23, ctx_m24],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
            strategy=STRATEGY_BALANCED,
            config={"valley_step_up_max_chip_temp_c": 80.0},
        )

        self.assertFalse(decision.can_proceed)
        self.assertEqual(decision.gate_action, ACTION_HOLD_THERMAL_HEADROOM)
        self.assertEqual(decision.action_status, "BLOCKED")

    def test_blocked_when_warming_up_or_presets_disabled(self):
        """T4.7: Salvaguardas de arranque y configuración inhabilitada."""
        ctx_warming = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=68.0,
            is_warming_up=True,
            electrical_group="elevator_1",
        )
        dec_warm = evaluate_fga_actuator_step(
            governance_contexts=[ctx_warming],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
            presets_enabled=True,
        )
        self.assertFalse(dec_warm.can_proceed)
        self.assertEqual(dec_warm.gate_action, "HOLD_WARMING_UP")

        ctx_ready = MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2500.0,
            configured_preset="2500",
            chip_temp_c=68.0,
            is_warming_up=False,
            electrical_group="elevator_1",
        )
        dec_disabled = evaluate_fga_actuator_step(
            governance_contexts=[ctx_ready],
            facility_state=self.facility_state,
            now_dt=self.valle_dt,
            now_ts=self.valle_ts,
            presets_enabled=False,
        )
        self.assertFalse(dec_disabled.can_proceed)
        self.assertEqual(dec_disabled.gate_action, "HOLD_PRESETS_DISABLED")


class TestFgaTelegramCommands(unittest.TestCase):
    """T5.1 - T5.3: Pruebas de integración para /agent run y /agent history."""

    def setUp(self):
        import threading
        from pathlib import Path
        from app.telegram.context import TelegramRequestContext
        from app.telegram.commands.agent import AgentCommand
        from app.miner_monitor import MinerState

        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_events.db")
        self.store = EventStore(self.db_path)
        self.sent_messages = []

        def mock_send(text, **kwargs):
            self.sent_messages.append(text)
            return True

        st23 = MinerState()
        st23.governor_last_temp_c = 78.0
        st23.last_max_chip_temp = 78.0
        st23.governor_last_power_w = 2500.0
        st23.last_power_w = 2500.0
        st23.balancer_preset = "2500W"
        st23.rate_ths = 98.0
        st23.vnish_restart_required = False

        st24 = MinerState()
        st24.governor_last_temp_c = 68.0
        st24.last_max_chip_temp = 68.0
        st24.governor_last_power_w = 2500.0
        st24.last_power_w = 2500.0
        st24.balancer_preset = "2500W"
        st24.rate_ths = 99.0
        st24.vnish_restart_required = False

        self.states = {
            "S19JPRO-23|192.168.1.123:4028": st23,
            "S19JPRO-24|192.168.1.124:4028": st24,
        }

        self.context = TelegramRequestContext(
            bot_token="test_token",
            chat_id="12345",
            config={
                "facility_agent_strategy": "balanced",
                "presets_enabled": True,
                "fan_governor_request_timeout": 2.5,
            },
            miners=[
                {"name": "S19JPRO-23", "host": "192.168.1.123", "port": 4028, "electrical_group": "elevator_1"},
                {"name": "S19JPRO-24", "host": "192.168.1.124", "port": 4028, "electrical_group": "elevator_1"},
            ],
            states=self.states,
            state_lock=threading.Lock(),
            state_path=Path(self.temp_dir.name) / "state.json",
            event_store=self.store,
            qa_mode=True,
        )
        self.context.send_message = mock_send
        self.cmd = AgentCommand()

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_agent_run_command_generates_and_simulates_action(self):
        """T5.1 & T5.3: /agent run ejecuta y responde con tarjeta compacta."""
        handled = self.cmd.handle(self.context, ["run"])
        self.assertTrue(handled)
        self.assertEqual(len(self.sent_messages), 1)

        msg = self.sent_messages[0]
        self.assertIn("FGA ACTUATOR: RUN", msg)
        self.assertIn("Estrategia: *BALANCED*", msg)
        # Verificar límite móvil <= 32 caracteres por línea en cabecera/separadores
        for line in msg.split("\n"):
            if "────────────────────────────" in line:
                self.assertLessEqual(len(line), 32)

    def test_agent_history_command_returns_persisted_actions(self):
        """T5.2 & T5.3: /agent history retorna acciones formateadas."""
        self.store.record_facility_agent_action(
            miner_name="S19JPRO-24",
            electrical_group="elevator_1",
            strategy="balanced",
            from_preset="2500W",
            to_preset="2700W",
            action_status="EXECUTED",
            gate_name="ALLOW_TRANSITION",
            reason="Silicio frío verificado",
        )

        handled = self.cmd.handle(self.context, ["history"])
        self.assertTrue(handled)
        self.assertEqual(len(self.sent_messages), 1)

        msg = self.sent_messages[0]
        self.assertIn("HISTORIAL ACCIONES FGA", msg)
        self.assertIn("S19JPRO-24", msg)
        self.assertIn("2500W ➔ 2700W", msg)


if __name__ == "__main__":
    unittest.main()
