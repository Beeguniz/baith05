import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingest"))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from database import TelemetryDatabase  # noqa: E402
from query_timerange import normalize_time, query_rows  # noqa: E402


class QueryTimeRangeTests(unittest.TestCase):
    def test_query_is_inclusive_and_filtered_by_device(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query.db"
            database = TelemetryDatabase(path)
            for sequence, received_at in enumerate(
                (
                    "2026-11-17T05:00:00.000Z",
                    "2026-11-17T05:00:01.000Z",
                    "2026-11-17T05:00:02.000Z",
                ),
                start=1,
            ):
                item = {
                    "device_id": "esp32_dht11",
                    "boot_id": "boot-query",
                    "seq": sequence,
                    "ts": sequence * 1000,
                    "temperature": 28.0,
                    "humidity": 60.0,
                    "valid": True,
                }
                database.insert_telemetry(
                    item, "VALID", received_at, json.dumps(item)
                )
            database.close()

            _, rows = query_rows(
                "esp32_dht11",
                "2026-11-17T05:00:00.000Z",
                "2026-11-17T05:00:01.000Z",
                path,
            )
            self.assertEqual([1, 2], [row["seq"] for row in rows])

    def test_timezone_is_normalized_to_utc(self) -> None:
        self.assertEqual(
            "2026-11-17T05:00:00.000Z",
            normalize_time("2026-11-17T12:00:00+07:00"),
        )

    def test_naive_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_time("2026-11-17T12:00:00")


if __name__ == "__main__":
    unittest.main()

