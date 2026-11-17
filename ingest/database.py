"""SQLite persistence for validated CSE3069 telemetry."""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "greenhouse.db"
SCHEMA_PATH = PROJECT_ROOT / "schema.sql"


class TelemetryDatabase:
    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.database_path, timeout=5.0, check_same_thread=False
        )
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._configure()
        self._initialize_schema()

    def _configure(self) -> None:
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = FULL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.connection.execute("PRAGMA foreign_keys = ON")

    def _initialize_schema(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connection:
            self.connection.executescript(schema)

    def insert_telemetry(
        self,
        payload: Mapping[str, Any],
        quality_status: str,
        received_at: str,
        raw_payload: str,
    ) -> bool:
        """Insert one row transactionally; return False for a duplicate key."""
        values = (
            payload["device_id"],
            payload["boot_id"],
            payload["seq"],
            payload["ts"],
            received_at,
            payload.get("temperature"),
            payload.get("humidity"),
            payload.get("temperature_unit"),
            payload.get("humidity_unit"),
            int(payload["valid"]),
            quality_status,
            raw_payload,
        )

        try:
            with self._lock:
                with self.connection:
                    self.connection.execute(
                        """
                        INSERT INTO telemetry (
                            device_id, boot_id, seq, device_ts_ms, received_at,
                            temperature, humidity, temperature_unit, humidity_unit,
                            valid, quality_status, raw_payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                return False
            raise

        return True

    def count_rows(self) -> int:
        with self._lock:
            row = self.connection.execute("SELECT COUNT(*) FROM telemetry").fetchone()
        return int(row[0])

    def close(self) -> None:
        with self._lock:
            self.connection.close()


