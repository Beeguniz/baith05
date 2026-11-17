"""Validate ESP32 telemetry without silently changing source values."""

from dataclasses import dataclass
from typing import Any, Mapping, Optional


REQUIRED_FIELDS = ("device_id", "boot_id", "seq", "ts", "valid")


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    quality_status: str
    reason: str


def _is_number(value: Any) -> bool:
    """Return True for int/float, explicitly excluding bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_payload(payload: Any) -> ValidationResult:
    if not isinstance(payload, Mapping):
        return ValidationResult(False, "REJECTED", "payload must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        return ValidationResult(
            False, "REJECTED", f"missing required fields: {', '.join(missing)}"
        )

    if not isinstance(payload["device_id"], str) or not payload["device_id"].strip():
        return ValidationResult(False, "REJECTED", "device_id must be a non-empty string")
    if not isinstance(payload["boot_id"], str) or not payload["boot_id"].strip():
        return ValidationResult(False, "REJECTED", "boot_id must be a non-empty string")
    if not isinstance(payload["seq"], int) or isinstance(payload["seq"], bool) or payload["seq"] < 0:
        return ValidationResult(False, "REJECTED", "seq must be a non-negative integer")
    if not isinstance(payload["ts"], int) or isinstance(payload["ts"], bool) or payload["ts"] < 0:
        return ValidationResult(False, "REJECTED", "ts must be a non-negative integer")
    if not isinstance(payload["valid"], bool):
        return ValidationResult(False, "REJECTED", "valid must be a boolean")

    temperature = payload.get("temperature")
    humidity = payload.get("humidity")

    if payload["valid"] is False:
        if temperature is None and humidity is None:
            return ValidationResult(True, "INVALID_SENSOR", "sensor reported a failed read")
        return ValidationResult(
            False,
            "REJECTED",
            "valid=false requires temperature=null and humidity=null",
        )

    if temperature is None or humidity is None:
        return ValidationResult(
            False, "REJECTED", "valid=true requires temperature and humidity"
        )
    if not _is_number(temperature) or not _is_number(humidity):
        return ValidationResult(
            False, "REJECTED", "temperature and humidity must be numbers"
        )

    suspect_reasons = []
    if not -40 <= temperature <= 100:
        suspect_reasons.append("temperature outside -40..100 C")
    if not 0 <= humidity <= 100:
        suspect_reasons.append("humidity outside 0..100 %")

    if suspect_reasons:
        return ValidationResult(True, "SUSPECT", "; ".join(suspect_reasons))

    return ValidationResult(True, "VALID", "payload accepted")


def message_key(payload: Mapping[str, Any]) -> Optional[tuple[str, str, int]]:
    """Build the project deduplication key after successful validation."""
    try:
        return payload["device_id"], payload["boot_id"], payload["seq"]
    except (KeyError, TypeError):
        return None


