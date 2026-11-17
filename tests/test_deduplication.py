import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingest"))

from database import TelemetryDatabase  # noqa: E402


class DeduplicationTests(unittest.TestCase):
    def test_same_device_boot_and_seq_is_not_inserted_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = TelemetryDatabase(Path(temporary_directory) / "dedup.db")
            item = {
                "device_id": "esp32_dht11",
                "boot_id": "boot-dedup",
                "seq": 10,
                "ts": 10000,
                "temperature": 28.0,
                "humidity": 60.0,
                "temperature_unit": "C",
                "humidity_unit": "%",
                "valid": True,
            }
            raw = json.dumps(item)
            self.assertTrue(
                database.insert_telemetry(
                    item, "VALID", "2026-11-17T05:00:00.000Z", raw
                )
            )
            self.assertFalse(
                database.insert_telemetry(
                    item, "VALID", "2026-11-17T05:00:01.000Z", raw
                )
            )
            self.assertEqual(1, database.count_rows())
            database.close()


if __name__ == "__main__":
    unittest.main()

