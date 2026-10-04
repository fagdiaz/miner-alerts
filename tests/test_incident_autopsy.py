"""Unit and contract tests for Spec 086: Incident Autopsy Engine & Conversational QA."""

import time
from unittest.mock import MagicMock

from app.core.event_store import EventStore
from app.forensics.autopsy_card import (
    build_autopsy_card,
    build_fleet_autopsy_summary_card,
)
from app.forensics.autopsy_engine import (
    CAUSE_AUTOTUNE_STALL,
    CAUSE_CHAIN_BREAK,
    CAUSE_LINK_DROP,
    CAUSE_POWER_LOSS,
    CAUSE_PSU_FAULT,
    CAUSE_THERMAL_SHUTDOWN,
    CAUSE_UNRESOLVED,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    AutopsyEvidence,
    AutopsyReport,
    IncidentAutopsyEngine,
    classify_incident_root_cause,
)
from app.forensics.conversational_qa import handle_conversational_query
from app.telegram.commands.autopsy import AutopsyCommand
from app.telegram.help_center import visible_line_width


def test_classify_link_drop():
    evidence = AutopsyEvidence(
        miner_name="S19JPRO-25",
        host="192.168.1.25",
        detected_ts=1700000000.0,
        elapsed_before=12000,
        elapsed_after=10,
        system_log_lines=(
            "[15:40:01] kernel: eth0: Link is Down",
            "[15:40:05] kernel: libphy: Link is Down",
        ),
        status_log_lines=("watchdog: Low hashrate detected",),
        miner_log_lines=(),
        last_power_w=2700.0,
        last_chip_temp_c=74.0,
        active_chains=3,
    )
    report = classify_incident_root_cause(evidence)
    assert report.root_cause_category == CAUSE_LINK_DROP
    assert report.confidence == CONFIDENCE_HIGH
    assert report.is_silicon_healthy is True
    assert "Ethernet" in report.headline or "Enlace" in report.headline


def test_classify_thermal_shutdown():
    # Case A: High temp in telemetry
    ev_telemetry = AutopsyEvidence(
        miner_name="S19JPRO-23",
        host="192.168.1.23",
        detected_ts=1700000000.0,
        elapsed_before=4500,
        elapsed_after=5,
        last_chip_temp_c=88.5,
    )
    rep_a = classify_incident_root_cause(ev_telemetry)
    assert rep_a.root_cause_category == CAUSE_THERMAL_SHUTDOWN

    # Case B: Overheating in logs
    ev_logs = AutopsyEvidence(
        miner_name="S19JPRO-23",
        host="192.168.1.23",
        detected_ts=1700000000.0,
        system_log_lines=("[12:00:00] Overheating: chip temp reached 86C",),
    )
    rep_b = classify_incident_root_cause(ev_logs)
    assert rep_b.root_cause_category == CAUSE_THERMAL_SHUTDOWN


def test_classify_chain_break():
    # Case A: Active chains drop
    ev_chains = AutopsyEvidence(
        miner_name="S19JPRO-24",
        host="192.168.1.24",
        detected_ts=1700000000.0,
        active_chains=2,
    )
    rep_a = classify_incident_root_cause(ev_chains)
    assert rep_a.root_cause_category == CAUSE_CHAIN_BREAK
    assert rep_a.is_silicon_healthy is False

    # Case B: Chain faulted in miner log
    ev_logs = AutopsyEvidence(
        miner_name="S19JPRO-24",
        host="192.168.1.24",
        detected_ts=1700000000.0,
        miner_log_lines=("Chain break detected at chip_addr 0x1b",),
    )
    rep_b = classify_incident_root_cause(ev_logs)
    assert rep_b.root_cause_category == CAUSE_CHAIN_BREAK
    assert rep_b.is_silicon_healthy is False


def test_classify_psu_fault():
    evidence = AutopsyEvidence(
        miner_name="S19JPRO-26",
        host="192.168.1.26",
        detected_ts=1700000000.0,
        status_log_lines=("PSU error detected: voltage check fail",),
        last_power_w=120.0,
    )
    report = classify_incident_root_cause(evidence)
    assert report.root_cause_category == CAUSE_PSU_FAULT
    assert report.confidence == CONFIDENCE_HIGH


def test_classify_autotune_stall():
    evidence = AutopsyEvidence(
        miner_name="S19JPRO-25",
        host="192.168.1.25",
        detected_ts=1700000000.0,
        status_log_lines=("Auto-tune timeout: PLL failed to lock frequency",),
    )
    report = classify_incident_root_cause(evidence)
    assert report.root_cause_category == CAUSE_AUTOTUNE_STALL
    assert report.confidence == CONFIDENCE_HIGH


def test_classify_power_loss():
    # Sudden drop with zero error lines in buffers (clean reboot)
    evidence = AutopsyEvidence(
        miner_name="S19JPRO-23",
        host="192.168.1.23",
        detected_ts=1700000000.0,
        elapsed_before=8000,
        elapsed_after=15,
        system_log_lines=(),
        status_log_lines=(),
        miner_log_lines=(),
    )
    report = classify_incident_root_cause(evidence)
    assert report.root_cause_category == CAUSE_POWER_LOSS
    assert report.confidence in (CONFIDENCE_HIGH, CONFIDENCE_MEDIUM)


def test_classify_unresolved():
    evidence = AutopsyEvidence(
        miner_name="S19JPRO-25",
        host="192.168.1.25",
        detected_ts=1700000000.0,
        elapsed_before=50,
        elapsed_after=20,
        system_log_lines=("Normal boot sequence line 1",),
    )
    report = classify_incident_root_cause(evidence)
    assert report.root_cause_category == CAUSE_UNRESOLVED
    assert report.confidence == CONFIDENCE_LOW


def test_mobile_first_card_strict_width():
    # Generate reports for each cause category and verify <= 32 cols
    causes = [
        CAUSE_LINK_DROP,
        CAUSE_CHAIN_BREAK,
        CAUSE_THERMAL_SHUTDOWN,
        CAUSE_PSU_FAULT,
        CAUSE_AUTOTUNE_STALL,
        CAUSE_POWER_LOSS,
        CAUSE_UNRESOLVED,
    ]

    reports = []
    for c in causes:
        rep = AutopsyReport(
            miner_name="S19JPRO-25",
            timestamp=1700000000.0,
            root_cause_category=c,
            confidence=CONFIDENCE_HIGH,
            headline=f"Headline para {c} muy largo para probar wrapping",
            summary_bullets=(
                "8x 'Link is Down' en los ultimos 5 minutos consecutivos",
                "Watchdog: Low hashrate detected con caida brusca",
            ),
            remediation_suggestion="Revisar conexion fisica de switch y cable patchcord RJ45.",
            is_silicon_healthy=(c != CAUSE_CHAIN_BREAK),
            raw_evidence_digest="abc123def456",
        )
        reports.append(rep)

        card = build_autopsy_card(rep)
        for idx, line in enumerate(card.splitlines()):
            width = visible_line_width(line)
            assert (
                width <= 32
            ), f"Line {idx} in card for {c} exceeds 32 cols (width={width}): '{line}'"

    fleet_card = build_fleet_autopsy_summary_card(reports)
    for idx, line in enumerate(fleet_card.splitlines()):
        width = visible_line_width(line)
        assert (
            width <= 32
        ), f"Line {idx} in fleet summary card exceeds 32 cols (width={width}): '{line}'"


def test_event_store_autopsy_persistence(tmp_path):
    db_file = tmp_path / "autopsy_test.db"
    store = EventStore(db_file)
    try:
        row_id = store.record_autopsy_assessment(
            miner_name="S19JPRO-25",
            miner_key="S19JPRO-25|192.168.1.25:4028",
            timestamp=1700000000.0,
            root_cause_category=CAUSE_LINK_DROP,
            confidence="HIGH",
            headline="Caída de Enlace Ethernet",
            summary_bullets=["8x 'Link is Down'", "Watchdog low hashrate"],
            remediation_suggestion="Revisar cable RJ45",
            is_silicon_healthy=True,
            evidence_digest="digest_test_1234",
        )
        assert row_id > 0

        # Query single
        rec = store.get_latest_autopsy_assessment("S19JPRO-25")
        assert rec is not None
        assert rec["subject_ref"] == "S19JPRO-25"
        assert rec["status"] == CAUSE_LINK_DROP
        assert rec["evidence_digest"] == "digest_test_1234"

        # Query fleet
        fleet = store.get_latest_autopsy_assessments_fleet(limit=10)
        assert len(fleet) >= 1
        assert fleet[0]["subject_ref"] == "S19JPRO-25"
    finally:
        store.close()


def test_conversational_qa_supervisor(tmp_path):
    db_file = tmp_path / "conv_test.db"
    store = EventStore(db_file)
    try:
        store.record_autopsy_assessment(
            miner_name="S19JPRO-25",
            timestamp=1700000000.0,
            root_cause_category=CAUSE_LINK_DROP,
            confidence="HIGH",
            headline="Caída de Enlace Ethernet",
            summary_bullets=["Cable desconectado"],
            remediation_suggestion="Revisar cable RJ45",
            is_silicon_healthy=True,
            evidence_digest="dig_conv_1",
        )

        mock_context = MagicMock()
        mock_context.event_store = store
        mock_context.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23"},
            {"name": "S19JPRO-25", "host": "192.168.1.25"},
        ]

        # 1. Why reboot miner 25
        ans_25 = handle_conversational_query("¿Por qué reinició la 25?", mock_context)
        assert ans_25 is not None
        assert "S19JPRO-25" in ans_25
        assert "ENLACE ETHERNET" in ans_25
        for line in ans_25.splitlines():
            assert visible_line_width(line) <= 32

        # 2. Why reboot miner 23 (no incidents recorded)
        ans_23 = handle_conversational_query("que paso con la 23?", mock_context)
        assert ans_23 is not None
        assert "S19JPRO-23" in ans_23
        assert "No registra incidentes" in ans_23

        # 3. Network status
        ans_net = handle_conversational_query("¿Cómo está la red?", mock_context)
        assert ans_net is not None
        assert "ESTADO DE RED" in ans_net
        for line in ans_net.splitlines():
            assert visible_line_width(line) <= 32

        # 4. Thermal status
        ans_thm = handle_conversational_query("¿hay maquinas con calor?", mock_context)
        assert ans_thm is not None
        assert "TÉRMICO" in ans_thm
        for line in ans_thm.splitlines():
            assert visible_line_width(line) <= 32

        # 5. Greeting
        ans_greet = handle_conversational_query("hola que tal hoy?", mock_context)
        assert ans_greet is not None
        assert "ASISTENTE" in ans_greet
        for line in ans_greet.splitlines():
            assert visible_line_width(line) <= 32

        # 6. Fleet status
        ans_fleet = handle_conversational_query("¿cómo está la flota?", mock_context)
        assert ans_fleet is not None
        assert "ESTADO DE FLOTA" in ans_fleet
        for line in ans_fleet.splitlines():
            assert visible_line_width(line) <= 32

        # 7. Power and elevators
        ans_pwr = handle_conversational_query("¿cuál es la potencia y carga de elevadores?", mock_context)
        assert ans_pwr is not None
        assert "POTENCIA Y ELEVADORES" in ans_pwr
        for line in ans_pwr.splitlines():
            assert visible_line_width(line) <= 32

        # 8. Governance directives
        ans_gov = handle_conversational_query("¿qué directivas y políticas hay?", mock_context)
        assert ans_gov is not None
        assert "GOBERNANZA Y DIRECTIVAS" in ans_gov
        for line in ans_gov.splitlines():
            assert visible_line_width(line) <= 32

        # 9. Unrecognized query returns friendly fallback guide
        ans_fallback = handle_conversational_query("consulta no reconocida xyz 12345", mock_context)
        assert ans_fallback is not None
        assert "No reconocí esa consulta" in ans_fallback
        for line in ans_fallback.splitlines():
            assert visible_line_width(line) <= 32

        # 10. Fallback disabled returns None
        assert handle_conversational_query("consulta no reconocida xyz 12345", mock_context, allow_fallback=False) is None

        # 11. Empty string returns None
        assert handle_conversational_query("", mock_context) is None
    finally:
        store.close()


def test_incident_autopsy_engine_bounded_timeout():
    # Collector function that delays longer than hard timeout
    def _slow_collector(**kwargs):
        time.sleep(2.0)
        mock_res = MagicMock()
        mock_res.ok = True
        mock_res.text = "delayed text"
        return mock_res

    engine = IncidentAutopsyEngine(hard_timeout_s=0.5)
    try:
        t0 = time.monotonic()
        rep = engine.run_autopsy(
            miner_name="S19JPRO-25",
            host="192.168.1.25",
            collect_fn=_slow_collector,
        )
        elapsed = time.monotonic() - t0
        # Hard timeout is 0.5s; total time must be <= 1.5s
        assert elapsed < 1.5
        assert rep is not None
        assert rep.miner_name == "S19JPRO-25"
    finally:
        engine.shutdown(wait=False)


def test_autopsy_command_execution(tmp_path):
    db_file = tmp_path / "cmd_test.db"
    store = EventStore(db_file)
    try:
        cmd = AutopsyCommand()
        mock_context = MagicMock()
        mock_context.event_store = store
        mock_context.miners = [
            {"name": "S19JPRO-25", "host": "192.168.1.25"},
        ]

        # Run command with miner 25
        handled = cmd.handle(mock_context, args=["25"])
        assert handled is True
        mock_context.send_message.assert_called()
        call_args = mock_context.send_message.call_args[0]
        assert "S19JPRO-25" in call_args[0]

        # Run command without args (fleet summary)
        handled_fleet = cmd.handle(mock_context, args=[])
        assert handled_fleet is True
    finally:
        store.close()


def test_autopsy_async_telegram_dispatch():
    from unittest.mock import patch
    import app.miner_monitor as mm
    from app.forensics.autopsy_engine import AutopsyReport, CAUSE_LINK_DROP, CONFIDENCE_HIGH

    rep = AutopsyReport(
        miner_name="S19JPRO-25",
        timestamp=1700000000.0,
        root_cause_category=CAUSE_LINK_DROP,
        confidence=CONFIDENCE_HIGH,
        headline="Caída de Enlace",
        summary_bullets=("Link is Down",),
        remediation_suggestion="Revisar cable",
        is_silicon_healthy=True,
        raw_evidence_digest="test_digest",
    )
    mock_fut = MagicMock()
    mock_fut.result.return_value = rep

    with patch.object(mm, "send_telegram") as mock_send_tg:
        # Simulate callback definition in monitor
        def _simulate_on_done(fut, m_name="S19JPRO-25", m_now=1700000000.0):
            res = fut.result()
            from app.forensics.autopsy_card import build_autopsy_card
            card = build_autopsy_card(res)
            mm.send_telegram(
                "mock_token",
                "123456",
                card,
                "AUTOPSY",
                f"autopsy_{m_name}_{int(m_now)}",
                is_command=True,
            )

        _simulate_on_done(mock_fut)
        mock_send_tg.assert_called_once()
        args, kwargs = mock_send_tg.call_args
        assert args[0] == "mock_token"
        assert args[1] == "123456"
        assert "AUTOPSIA: S19JPRO-25" in args[2]
        assert args[3] == "AUTOPSY"
        assert kwargs.get("is_command") is True
