"""Vnish Hashboard Chain and Sensor Telemetry Models (Spec 054).

Provides strongly-typed dataclasses and serialization for per-chain
and per-sensor telemetry exposed by Vnish firmware REST API (/api/v1/chains).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class ChainSensor:
    """Individual thermal/I2C sensor located on a hashboard chain."""
    state: str  # "measure", "error", etc.
    board_temp: Optional[float] = None
    chip_temp: Optional[float] = None
    loc: Optional[int] = None

    @property
    def is_healthy(self) -> bool:
        """Returns True if the sensor is in normal measuring state."""
        return self.state.lower() == "measure"

    def to_dict(self) -> Dict[str, Any]:
        """Convert sensor to JSON-serializable dictionary."""
        return {
            "state": self.state,
            "board": self.board_temp,
            "chip": self.chip_temp,
            "loc": self.loc,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChainSensor:
        """Construct ChainSensor from API dictionary."""
        state = str(data.get("state", "unknown"))
        board = data.get("board")
        chip = data.get("chip")
        loc = data.get("loc")
        return cls(
            state=state,
            board_temp=float(board) if board is not None else None,
            chip_temp=float(chip) if chip is not None else None,
            loc=int(loc) if loc is not None else None,
        )


@dataclass
class ChainTelemetry:
    """Consolidated telemetry for a single hashboard chain (e.g. Chain 1, 2, or 3)."""
    chain_id: int
    state: str  # "mining", "error", "stopped", etc.
    hr_realtime_mhs: float
    hr_nominal_mhs: float
    freq_mhz_avg: float
    sensors: List[ChainSensor] = field(default_factory=list)
    sensors_error_count: int = 0
    chips_total: int = 0
    chips_error_count: int = 0
    chips_throttled_count: int = 0
    chips_hw_errors_total: int = 0

    @property
    def hr_deficit_pct(self) -> float:
        """Percentage deviation of real-time hashrate relative to nominal."""
        if self.hr_nominal_mhs > 0.0:
            return max(0.0, ((self.hr_nominal_mhs - self.hr_realtime_mhs) / self.hr_nominal_mhs) * 100.0)
        return 0.0

    @property
    def is_healthy(self) -> bool:
        """True if mining normally with zero sensor errors and deficit < 10%."""
        return (
            self.state.lower() == "mining"
            and self.sensors_error_count == 0
            and self.hr_deficit_pct < 10.0
        )

    @property
    def max_chip_temp(self) -> Optional[float]:
        """Maximum chip temperature recorded across valid sensors on this chain."""
        temps = [s.chip_temp for s in self.sensors if s.chip_temp is not None]
        return max(temps) if temps else None

    @property
    def max_board_temp(self) -> Optional[float]:
        """Maximum board temperature recorded across valid sensors on this chain."""
        temps = [s.board_temp for s in self.sensors if s.board_temp is not None]
        return max(temps) if temps else None

    def sensors_json(self) -> str:
        """Serialize sensors list to compact JSON string."""
        return json.dumps([s.to_dict() for s in self.sensors], ensure_ascii=True, separators=(",", ":"))

    def to_dict(self) -> Dict[str, Any]:
        """Convert telemetry to JSON-serializable dictionary."""
        return {
            "chain_id": self.chain_id,
            "state": self.state,
            "hr_realtime_mhs": self.hr_realtime_mhs,
            "hr_nominal_mhs": self.hr_nominal_mhs,
            "hr_deficit_pct": round(self.hr_deficit_pct, 2),
            "freq_mhz_avg": round(self.freq_mhz_avg, 2),
            "sensors_error_count": self.sensors_error_count,
            "sensors": [s.to_dict() for s in self.sensors],
            "chips_total": self.chips_total,
            "chips_error_count": self.chips_error_count,
            "chips_throttled_count": self.chips_throttled_count,
            "chips_hw_errors_total": self.chips_hw_errors_total,
            "max_chip_temp": self.max_chip_temp,
            "max_board_temp": self.max_board_temp,
            "is_healthy": self.is_healthy,
        }

    @classmethod
    def from_api_dict(cls, data: Mapping[str, Any]) -> ChainTelemetry:
        """Construct ChainTelemetry from a single item of /api/v1/chains response."""
        chain_id = int(data.get("id", 0))
        status_obj = data.get("status")
        if isinstance(status_obj, dict):
            state = str(status_obj.get("state", "unknown"))
        else:
            state = str(status_obj or "unknown")

        hr_realtime = float(data.get("hr_realtime") or 0.0)
        hr_nominal = float(data.get("hr_nominal") or 0.0)
        freq = float(data.get("freq") or 0.0)

        raw_sensors = data.get("sensors") or []
        sensors: List[ChainSensor] = []
        err_sensors = 0
        for s in raw_sensors:
            if isinstance(s, dict):
                sensor = ChainSensor.from_dict(s)
                sensors.append(sensor)
                if not sensor.is_healthy:
                    err_sensors += 1

        raw_chips = data.get("chips") or []
        chips_total = len(raw_chips)
        chips_err_count = 0
        chips_throttled_count = 0
        chips_hw_errs_total = 0

        for c in raw_chips:
            if isinstance(c, dict):
                errs = int(c.get("errs") or 0)
                if errs > 0:
                    chips_err_count += 1
                    chips_hw_errs_total += errs
                if c.get("throttled") is True:
                    chips_throttled_count += 1

        return cls(
            chain_id=chain_id,
            state=state,
            hr_realtime_mhs=hr_realtime,
            hr_nominal_mhs=hr_nominal,
            freq_mhz_avg=freq,
            sensors=sensors,
            sensors_error_count=err_sensors,
            chips_total=chips_total,
            chips_error_count=chips_err_count,
            chips_throttled_count=chips_throttled_count,
            chips_hw_errors_total=chips_hw_errs_total,
        )
