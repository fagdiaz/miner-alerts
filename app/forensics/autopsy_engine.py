"""Autonomous incident autopsy engine and root-cause classifier (Spec 086 / PROP-016)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from tools.vnish_log_collector import collect_vnish_tab

logger = logging.getLogger(__name__)

# Severity / category taxonomy constants
CAUSE_LINK_DROP = "LINK_DROP"
CAUSE_CHAIN_BREAK = "CHAIN_BREAK"
CAUSE_THERMAL_SHUTDOWN = "THERMAL_SHUTDOWN"
CAUSE_PSU_FAULT = "PSU_FAULT"
CAUSE_AUTOTUNE_STALL = "AUTOTUNE_STALL"
CAUSE_POWER_LOSS = "POWER_LOSS"
CAUSE_UNRESOLVED = "UNRESOLVED"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"


@dataclass(frozen=True)
class AutopsyEvidence:
    """Immutable forensic evidence collected during an incident window."""

    miner_name: str
    host: str
    detected_ts: float
    elapsed_before: int = 0
    elapsed_after: int = 0
    system_log_lines: Sequence[str] = field(default_factory=tuple)
    status_log_lines: Sequence[str] = field(default_factory=tuple)
    miner_log_lines: Sequence[str] = field(default_factory=tuple)
    last_power_w: Optional[float] = None
    last_chip_temp_c: Optional[float] = None
    active_chains: int = 3


@dataclass(frozen=True)
class AutopsyReport:
    """Immutable synthesized post-mortem incident report."""

    miner_name: str
    timestamp: float
    root_cause_category: str
    confidence: str
    headline: str
    summary_bullets: Sequence[str]
    remediation_suggestion: str
    is_silicon_healthy: bool
    raw_evidence_digest: str


# Regex matchers for root-cause classification
_RE_THERMAL = re.compile(
    r"(?:overheating|shutdown due to high temp|thermal runaway|temp\s*>=?\s*8[5-9]|temp\s*>=?\s*9\d)",
    re.IGNORECASE,
)
_RE_CHAIN_BREAK = re.compile(
    r"(?:chain break detected|chip_addr\s+0x[0-9a-fA-F]+|chain faulted|chain\s+\[?\d+\]?\s+offline)",
    re.IGNORECASE,
)
_RE_LINK_DROP = re.compile(
    r"(?:(?:libphy|eth0).*link is down|carrier lost|network unreachable)",
    re.IGNORECASE,
)
_RE_WATCHDOG_HASHRATE = re.compile(
    r"(?:watchdog.*low hashrate|low hashrate|hashrate dropped to 0)",
    re.IGNORECASE,
)
_RE_PSU_FAULT = re.compile(
    r"(?:psu error|voltage check fail|power off spontaneously|power supply fault|voltage dropped)",
    re.IGNORECASE,
)
_RE_AUTOTUNE_STALL = re.compile(
    r"(?:auto-tune timeout|pll failed|autotune fail|frequency lock lost)",
    re.IGNORECASE,
)
_RE_POWER_LOSS = re.compile(
    r"(?:power loss detected|sudden power cut|power failure)",
    re.IGNORECASE,
)


def _extract_matches(lines: Sequence[str], pattern: re.Pattern) -> list[str]:
    matches: list[str] = []
    for line in lines:
        if pattern.search(line):
            matches.append(line.strip())
    return matches


def classify_incident_root_cause(evidence: AutopsyEvidence) -> AutopsyReport:
    """Deterministically classify an incident's root cause from evidence."""
    all_lines: list[str] = []
    all_lines.extend(evidence.system_log_lines)
    all_lines.extend(evidence.status_log_lines)
    all_lines.extend(evidence.miner_log_lines)

    # 1. THERMAL_SHUTDOWN Check
    thermal_matches = _extract_matches(all_lines, _RE_THERMAL)
    temp_exceeded = evidence.last_chip_temp_c is not None and evidence.last_chip_temp_c >= 85.0
    if thermal_matches or temp_exceeded:
        bullets: list[str] = []
        if temp_exceeded:
            bullets.append(f"Temp chip pico: {evidence.last_chip_temp_c:.1f}°C (>=85°C)")
        for m in thermal_matches[:2]:
            bullets.append(f"Log: {m[:40]}")
        bullets.append("Corte térmico de seguridad activado")

        digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:THERMAL:{len(bullets)}"
        digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

        return AutopsyReport(
            miner_name=evidence.miner_name,
            timestamp=evidence.detected_ts,
            root_cause_category=CAUSE_THERMAL_SHUTDOWN,
            confidence=CONFIDENCE_HIGH if thermal_matches and temp_exceeded else CONFIDENCE_MEDIUM,
            headline="Sobretemperatura Crítica",
            summary_bullets=tuple(bullets),
            remediation_suggestion="Revisar disipadores, flujo de aire y fans.",
            is_silicon_healthy=(evidence.active_chains >= 3),
            raw_evidence_digest=digest,
        )

    # 2. CHAIN_BREAK Check
    chain_matches = _extract_matches(all_lines, _RE_CHAIN_BREAK)
    chain_count_fault = evidence.active_chains < 3
    if chain_matches or chain_count_fault:
        bullets = []
        if chain_count_fault:
            bullets.append(f"Cadenas activas: {evidence.active_chains}/3 detectadas")
        for m in chain_matches[:2]:
            bullets.append(f"Log: {m[:40]}")
        bullets.append("Falla de comunicación en bus de chips")

        digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:CHAIN:{len(bullets)}"
        digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

        return AutopsyReport(
            miner_name=evidence.miner_name,
            timestamp=evidence.detected_ts,
            root_cause_category=CAUSE_CHAIN_BREAK,
            confidence=CONFIDENCE_HIGH,
            headline="Rotura de Cadena de Chips",
            summary_bullets=tuple(bullets),
            remediation_suggestion="Revisar conectores ribbon o microfisura.",
            is_silicon_healthy=False,
            raw_evidence_digest=digest,
        )

    # 3. LINK_DROP Check
    link_matches = _extract_matches(all_lines, _RE_LINK_DROP)
    watchdog_matches = _extract_matches(all_lines, _RE_WATCHDOG_HASHRATE)
    if link_matches or (watchdog_matches and any("carrier" in l.lower() or "link" in l.lower() for l in all_lines)):
        bullets = []
        count = len(link_matches)
        bullets.append(f"{count}x 'Link is Down' detectado" if count > 0 else "Enlace físico interrumpido")
        if watchdog_matches:
            bullets.append("Watchdog: Low hashrate por red")
        for m in link_matches[:2]:
            bullets.append(f"Log: {m[:40]}")

        digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:LINK:{len(bullets)}"
        digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

        return AutopsyReport(
            miner_name=evidence.miner_name,
            timestamp=evidence.detected_ts,
            root_cause_category=CAUSE_LINK_DROP,
            confidence=CONFIDENCE_HIGH,
            headline="Caída de Enlace Ethernet",
            summary_bullets=tuple(bullets),
            remediation_suggestion="Revisar patchcord RJ45 o switch.",
            is_silicon_healthy=True,
            raw_evidence_digest=digest,
        )

    # 4. PSU_FAULT Check
    psu_matches = _extract_matches(all_lines, _RE_PSU_FAULT)
    if psu_matches:
        bullets = []
        for m in psu_matches[:2]:
            bullets.append(f"Log: {m[:40]}")
        if evidence.last_power_w is not None:
            bullets.append(f"Última potencia: {evidence.last_power_w:.0f}W")
        bullets.append("Voltaje fuera de tolerancia")

        digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:PSU:{len(bullets)}"
        digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

        return AutopsyReport(
            miner_name=evidence.miner_name,
            timestamp=evidence.detected_ts,
            root_cause_category=CAUSE_PSU_FAULT,
            confidence=CONFIDENCE_HIGH,
            headline="Falla de Fuente de Poder (PSU)",
            summary_bullets=tuple(bullets),
            remediation_suggestion="Verificar fase de elevador, bornes y PSU.",
            is_silicon_healthy=True,
            raw_evidence_digest=digest,
        )

    # 5. AUTOTUNE_STALL Check
    autotune_matches = _extract_matches(all_lines, _RE_AUTOTUNE_STALL)
    if autotune_matches:
        bullets = []
        for m in autotune_matches[:2]:
            bullets.append(f"Log: {m[:40]}")
        bullets.append("Timeout o bloqueo en ajuste PLL")

        digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:AUTOTUNE:{len(bullets)}"
        digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

        return AutopsyReport(
            miner_name=evidence.miner_name,
            timestamp=evidence.detected_ts,
            root_cause_category=CAUSE_AUTOTUNE_STALL,
            confidence=CONFIDENCE_HIGH,
            headline="Falla de Autotuning de Frecuencia",
            summary_bullets=tuple(bullets),
            remediation_suggestion="Fijar perfil de autotune más conservador.",
            is_silicon_healthy=True,
            raw_evidence_digest=digest,
        )

    # 6. POWER_LOSS Check
    power_matches = _extract_matches(all_lines, _RE_POWER_LOSS)
    clean_cold_boot = (
        evidence.elapsed_before > 120
        and evidence.elapsed_after < 60
        and len(all_lines) == 0
    )
    if power_matches or clean_cold_boot:
        bullets = []
        if clean_cold_boot:
            bullets.append("Reinicio en frío sin registros de error")
            bullets.append("Buffer de logs reseteado al arranque")
        else:
            for m in power_matches[:2]:
                bullets.append(f"Log: {m[:40]}")
        bullets.append("Corte abrupto de energía detectado")

        digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:POWER:{len(bullets)}"
        digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

        return AutopsyReport(
            miner_name=evidence.miner_name,
            timestamp=evidence.detected_ts,
            root_cause_category=CAUSE_POWER_LOSS,
            confidence=CONFIDENCE_HIGH if power_matches else CONFIDENCE_MEDIUM,
            headline="Corte de Suministro Eléctrico",
            summary_bullets=tuple(bullets),
            remediation_suggestion="Verificar térmica de línea o elevador.",
            is_silicon_healthy=True,
            raw_evidence_digest=digest,
        )

    # 7. UNRESOLVED Fallback
    bullets = [
        "Sin anomalías críticas en logs",
        f"Elapsed: {evidence.elapsed_before}s -> {evidence.elapsed_after}s",
        "Monitoreando estabilización post-reinicio",
    ]
    digest_str = f"{evidence.miner_name}:{evidence.detected_ts}:UNRESOLVED:{len(bullets)}"
    digest = hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:16]

    return AutopsyReport(
        miner_name=evidence.miner_name,
        timestamp=evidence.detected_ts,
        root_cause_category=CAUSE_UNRESOLVED,
        confidence=CONFIDENCE_LOW,
        headline="Causa No Determinada",
        summary_bullets=tuple(bullets),
        remediation_suggestion="Monitorear telemetría y warmup.",
        is_silicon_healthy=True,
        raw_evidence_digest=digest,
    )


class IncidentAutopsyEngine:
    """Non-blocking, bounded asynchronous forensic engine for unexpected reboots."""

    def __init__(
        self,
        event_store: Any = None,
        max_workers: int = 2,
        hard_timeout_s: float = 2.5,
    ) -> None:
        self._event_store = event_store
        self._hard_timeout_s = min(max(0.5, float(hard_timeout_s)), 3.0)
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="autopsy_worker",
        )

    def shutdown(self, wait: bool = False) -> None:
        """Shut down background worker pool."""
        self._pool.shutdown(wait=wait)

    def _fetch_tabs(
        self,
        host: str,
        collect_fn: Optional[Callable[..., Any]] = None,
    ) -> tuple[list[str], list[str], list[str]]:
        clean_host = host.split(":")[0].strip()
        fn = collect_fn or collect_vnish_tab

        def _get_tab_lines(tab: str) -> list[str]:
            try:
                res = fn(
                    host=clean_host,
                    source_tab=tab,
                    connect_timeout=min(1.2, self._hard_timeout_s),
                    idle_timeout=0.3,
                    max_bytes=65536,
                )
                if res and getattr(res, "ok", False) and getattr(res, "text", ""):
                    lines = [ln.strip() for ln in res.text.splitlines() if ln.strip()]
                    return lines[-50:]  # keep recent 50 lines
            except Exception as exc:
                logger.debug("Error fetching vnish tab %s for %s: %s", tab, clean_host, exc)
            return []

        # Sequential or quick gathering with per-tab bounded timeout
        system_lines = _get_tab_lines("system")
        status_lines = _get_tab_lines("status")
        miner_lines = _get_tab_lines("miner")
        return system_lines, status_lines, miner_lines

    def run_autopsy(
        self,
        *,
        miner_name: str,
        host: str,
        detected_ts: Optional[float] = None,
        elapsed_before: int = 0,
        elapsed_after: int = 0,
        last_power_w: Optional[float] = None,
        last_chip_temp_c: Optional[float] = None,
        active_chains: int = 3,
        collect_fn: Optional[Callable[..., Any]] = None,
    ) -> AutopsyReport:
        """Run autopsy synchronously with hard deadline protection."""
        ts = float(detected_ts if detected_ts is not None else time.time())
        future = self._pool.submit(self._fetch_tabs, host, collect_fn)

        system_lines: list[str] = []
        status_lines: list[str] = []
        miner_lines: list[str] = []

        try:
            system_lines, status_lines, miner_lines = future.result(
                timeout=self._hard_timeout_s
            )
        except FuturesTimeoutError:
            logger.warning(
                "Autopsy log collection timed out after %.1fs for %s (%s)",
                self._hard_timeout_s,
                miner_name,
                host,
            )
        except Exception as exc:
            logger.warning(
                "Autopsy log collection failed for %s (%s): %s",
                miner_name,
                host,
                exc,
            )

        evidence = AutopsyEvidence(
            miner_name=miner_name,
            host=host,
            detected_ts=ts,
            elapsed_before=elapsed_before,
            elapsed_after=elapsed_after,
            system_log_lines=tuple(system_lines),
            status_log_lines=tuple(status_lines),
            miner_log_lines=tuple(miner_lines),
            last_power_w=last_power_w,
            last_chip_temp_c=last_chip_temp_c,
            active_chains=active_chains,
        )

        report = classify_incident_root_cause(evidence)

        # Persist to EventStore if available
        if self._event_store is not None:
            try:
                miner_key = f"{miner_name}|{host}"
                self._event_store.record_autopsy_assessment(
                    miner_name=report.miner_name,
                    miner_key=miner_key,
                    timestamp=report.timestamp,
                    root_cause_category=report.root_cause_category,
                    confidence=report.confidence,
                    headline=report.headline,
                    summary_bullets=report.summary_bullets,
                    remediation_suggestion=report.remediation_suggestion,
                    is_silicon_healthy=report.is_silicon_healthy,
                    evidence_digest=report.raw_evidence_digest,
                )
            except Exception as exc:
                logger.error("Failed to persist autopsy report for %s: %s", miner_name, exc)

        return report

    def run_autopsy_async(
        self,
        *,
        miner_name: str,
        host: str,
        detected_ts: Optional[float] = None,
        elapsed_before: int = 0,
        elapsed_after: int = 0,
        last_power_w: Optional[float] = None,
        last_chip_temp_c: Optional[float] = None,
        active_chains: int = 3,
        collect_fn: Optional[Callable[..., Any]] = None,
    ):
        """Submit autopsy to background pool returning a Future[AutopsyReport]."""
        return self._pool.submit(
            self.run_autopsy,
            miner_name=miner_name,
            host=host,
            detected_ts=detected_ts,
            elapsed_before=elapsed_before,
            elapsed_after=elapsed_after,
            last_power_w=last_power_w,
            last_chip_temp_c=last_chip_temp_c,
            active_chains=active_chains,
            collect_fn=collect_fn,
        )
