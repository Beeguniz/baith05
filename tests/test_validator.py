import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingest"))

from validator import message_key, validate_payload  # noqa: E402


def valid_payload() -> dict:
    return {
        "device_id": "esp32_dht11",
        "boot_id": "boot-test",
        "seq": 1,
        "ts": 5000,
        "ts_unit": "uptime_ms",
        "temperature": 28.5,
        "humidity": 65.0,
        "temperature_unit": "C",
        "humidity_unit": "%",
        "valid": True,
    }


class ValidatorTests(unittest.TestCase):
    def test_valid_payload(self) -> None:
        result = validate_payload(valid_payload())
        self.assertTrue(result.accepted)
        self.assertEqual("VALID", result.quality_status)

    def test_missing_required_field_is_rejected(self) -> None:
        payload = valid_payload()
        del payload["boot_id"]
        result = validate_payload(payload)
        self.assertFalse(result.accepted)
        self.assertIn("boot_id", result.reason)

    def test_valid_false_with_null_values_is_accepted(self) -> None:
        payload = valid_payload()
        payload.update(valid=False, temperature=None, humidity=None)
        result = validate_payload(payload)
        self.assertTrue(result.accepted)
        self.assertEqual("INVALID_SENSOR", result.quality_status)

    def test_valid_true_with_null_is_rejected(self) -> None:
        payload = valid_payload()
        payload["temperature"] = None
        result = validate_payload(payload)
        self.assertFalse(result.accepted)

    def test_wrong_measurement_type_is_rejected_without_coercion(self) -> None:
        payload = valid_payload()
        payload["temperature"] = "28.5"
        result = validate_payload(payload)
        self.assertFalse(result.accepted)
        self.assertEqual("REJECTED", result.quality_status)

    def test_boolean_is_not_accepted_as_number(self) -> None:
        payload = valid_payload()
        payload["humidity"] = True
        self.assertFalse(validate_payload(payload).accepted)

    def test_out_of_range_is_preserved_as_suspect(self) -> None:
        payload = valid_payload()
        payload.update(temperature=120.0, humidity=101.0)
        result = validate_payload(payload)
        self.assertTrue(result.accepted)
        self.assertEqual("SUSPECT", result.quality_status)
        self.assertEqual(120.0, payload["temperature"])
        self.assertEqual(101.0, payload["humidity"])

    def test_message_key(self) -> None:
        self.assertEqual(
            ("esp32_dht11", "boot-test", 1), message_key(valid_payload())
        )


if __name__ == "__main__":
    unittest.main()

