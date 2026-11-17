import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingest"))

from database import TelemetryDatabase  # noqa: E402


def payload(seq: int = 1, ts: int = 5000) -> dict:
    return {
        "device_id": "esp32_dht11",
        "boot_id": "boot-db-test",
        "seq": seq,
        "ts": ts,
        "temperature": 28.5,
        "humidity": 65.0,
        "temperature_unit": "C",
        "humidity_unit": "%",
        "valid": True,
    }


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        self.database = TelemetryDatabase(self.database_path)

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def insert(self, item: dict, received_at: str) -> bool:
        return self.database.insert_telemetry(
            item, "VALID", received_at, json.dumps(item)
        )

    def test_database_insert_preserves_values(self) -> None:
        item = payload()
        self.assertTrue(self.insert(item, "2026-11-17T05:00:00.000Z"))
        row = self.database.connection.execute(
            "SELECT * FROM telemetry WHERE seq = 1"
        ).fetchone()
        self.assertEqual(28.5, row["temperature"])
        self.assertEqual(65.0, row["humidity"])
        self.assertEqual("VALID", row["quality_status"])

    def test_database_pragmas(self) -> None:
        self.assertEqual(
            "wal", self.database.connection.execute("PRAGMA journal_mode").fetchone()[0]
        )
        self.assertEqual(
            2, self.database.connection.execute("PRAGMA synchronous").fetchone()[0]
        )
        self.assertEqual(
            5000,
            self.database.connection.execute("PRAGMA busy_timeout").fetchone()[0],
        )

    def test_persistence_after_reopen(self) -> None:
        self.insert(payload(), "2026-11-17T05:00:00.000Z")
        self.database.close()
        self.database = TelemetryDatabase(self.database_path)
        self.assertEqual(1, self.database.count_rows())

    def test_late_message_is_stored(self) -> None:
        self.insert(payload(seq=2, ts=9000), "2026-11-17T05:00:02.000Z")
        self.assertTrue(
            self.insert(payload(seq=1, ts=5000), "2026-11-17T05:00:03.000Z")
        )
        rows = self.database.connection.execute(
            "SELECT seq, device_ts_ms FROM telemetry ORDER BY received_at"
        ).fetchall()
        self.assertEqual([(2, 9000), (1, 5000)], [tuple(row) for row in rows])

    def test_null_measurements_are_sql_null(self) -> None:
        item = payload()
        item.update(valid=False, temperature=None, humidity=None)
        self.assertTrue(
            self.database.insert_telemetry(
                item,
                "INVALID_SENSOR",
                "2026-11-17T05:00:00.000Z",
                json.dumps(item),
            )
        )
        row = self.database.connection.execute(
            "SELECT temperature, humidity FROM telemetry"
        ).fetchone()
        self.assertIsNone(row["temperature"])
        self.assertIsNone(row["humidity"])


if __name__ == "__main__":
    unittest.main()

