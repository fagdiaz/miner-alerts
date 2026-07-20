from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional


_CHAIN_VOLTAGE_RE = re.compile(r"^chain_(?:vol|voltage)(\d+)$", re.IGNORECASE)
_CHAIN_CONSUMPTION_RE = re.compile(r"^chain_consumption(\d+)$", re.IGNORECASE)
_CHAIN_FREQUENCY_RE = re.compile(r"^freq_avg(\d+)$", re.IGNORECASE)
_CHAIN_HW_RE = re.compile(r"^chain_hw(\d+)$", re.IGNORECASE)
_FAN_RPM_RE = re.compile(r"^fan(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class VnishTelemetry:
    max_temp_c: Optional[float] = None
    chain_voltage_mv_avg: Optional[float] = None
    chain_power_w_total: Optional[float] = None
    frequency_mhz_avg: Optional[float] = None
    hw_errors_total: Optional[int] = None
    fan_rpm_max: Optional[int] = None
    fan_pwm_percent: Optional[float] = None
    diagnostic_flags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_temp_c": self.max_temp_c,
            "chain_voltage_mv_avg": self.chain_voltage_mv_avg,
            "chain_power_w_total": self.chain_power_w_total,
            "frequency_mhz_avg": self.frequency_mhz_avg,
            "hw_errors_total": self.hw_errors_total,
            "fan_rpm_max": self.fan_rpm_max,
            "fan_pwm_percent": self.fan_pwm_percent,
            "diagnostic_flags": list(self.diagnostic_flags),
        }


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _numbers(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)):
        out: list[float] = []
        for item in value:
            number = _finite_number(item)
            if number is not None:
                out.append(number)
        return out
    number = _finite_number(value)
    return [number] if number is not None else []


def _dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            if isinstance(nested, (dict, list, tuple)):
                yield from _dicts(nested)
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, (dict, list, tuple)):
                yield from _dicts(item)


def _average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def normalize_vnish_stats(
    response: Any,
    *,
    expected_boards: Optional[int] = None,
) -> VnishTelemetry:
    """Extract bounded board-level evidence from a cgminer/Vnish stats response."""
    root = response.get("STATS") if isinstance(response, dict) and "STATS" in response else response
    temperatures: list[float] = []
    voltages: dict[str, float] = {}
    consumption: dict[str, float] = {}
    frequencies: dict[str, float] = {}
    hw_errors: dict[str, float] = {}
    fan_rpms: dict[str, float] = {}
    fan_pwm_values: list[float] = []

    for item in _dicts(root):
        for raw_key, raw_value in item.items():
            key = str(raw_key).strip().lower()
            values = _numbers(raw_value)
            if not values:
                continue

            if "temp" in key:
                temperatures.extend(value for value in values if 0.0 < value < 250.0)

            match = _CHAIN_VOLTAGE_RE.fullmatch(key)
            if match and values[0] > 0:
                voltages[match.group(1)] = values[0]
                continue
            match = _CHAIN_CONSUMPTION_RE.fullmatch(key)
            if match and values[0] >= 0:
                consumption[match.group(1)] = values[0]
                continue
            match = _CHAIN_FREQUENCY_RE.fullmatch(key)
            if match and values[0] > 0:
                frequencies[match.group(1)] = values[0]
                continue
            match = _CHAIN_HW_RE.fullmatch(key)
            if match and values[0] >= 0:
                hw_errors[match.group(1)] = values[0]
                continue
            match = _FAN_RPM_RE.fullmatch(key)
            if match and values[0] > 0:
                fan_rpms[match.group(1)] = values[0]
                continue
            if key == "fan_pwm":
                fan_pwm_values.extend(value for value in values if 0.0 <= value <= 100.0)

    flags: list[str] = []
    telemetry_fields_found = any(
        (temperatures, voltages, consumption, frequencies, hw_errors, fan_rpms, fan_pwm_values)
    )
    if not telemetry_fields_found:
        flags.append("telemetry_incomplete")
    observed_chain_ids = set(voltages) | set(consumption) | set(frequencies) | set(hw_errors)
    if expected_boards is not None and expected_boards > 0 and len(observed_chain_ids) < expected_boards:
        flags.append("chain_signal_below_expected")
    max_temp = max(temperatures) if temperatures else None
    if max_temp is not None and max_temp >= 85.0:
        flags.append("high_temperature")
    hw_total = int(sum(hw_errors.values())) if hw_errors else None
    if hw_total is not None and hw_total > 0:
        flags.append("hw_errors_present")
    if telemetry_fields_found and not fan_rpms:
        flags.append("fan_signal_missing")

    return VnishTelemetry(
        max_temp_c=round(max_temp, 2) if max_temp is not None else None,
        chain_voltage_mv_avg=_average(list(voltages.values())),
        chain_power_w_total=round(sum(consumption.values()), 3) if consumption else None,
        frequency_mhz_avg=_average(list(frequencies.values())),
        hw_errors_total=hw_total,
        fan_rpm_max=int(max(fan_rpms.values())) if fan_rpms else None,
        fan_pwm_percent=_average(fan_pwm_values),
        diagnostic_flags=tuple(flags),
    )
