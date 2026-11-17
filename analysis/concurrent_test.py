"""Compare SQLite ingestion with and without concurrent aggregate queries."""

import argparse
import csv
import json
import sqlite3
import statistics
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import paho.mqtt.client as mqtt


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGEST_DIR = PROJECT_ROOT / "ingest"
sys.path.insert(0, str(INGEST_DIR))

from database import DATABASE_PATH, TelemetryDatabase  # noqa: E402
from validator import validate_payload  # noqa: E402


MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "cse3069/th05/esp32/telemetry"
RESULTS_DIR = PROJECT_ROOT / "results"
CSV_PATH = RESULTS_DIR / "concurrent_test.csv"
CHART_PATH = RESULTS_DIR / "concurrent_test.png"


@dataclass
class ExperimentResult:
    experiment: str
    duration_seconds: float
    total_received: int
    stored_successfully: int
    rejected: int
    duplicates: int
    database_errors: int
    avg_write_latency_ms: float
    p95_write_latency_ms: float
    query_count: int
    query_errors: int
    avg_query_latency_ms: float
    p95_query_latency_ms: float


class Experiment:
    def __init__(self, name: str, duration_seconds: float, heavy_queries: bool) -> None:
        self.name = name
        self.duration_seconds = duration_seconds
        self.heavy_queries = heavy_queries
        self.database = TelemetryDatabase()
        self.connected = threading.Event()
        self.stop_queries = threading.Event()
        self.lock = threading.Lock()
        self.total_received = 0
        self.stored = 0
        self.rejected = 0
        self.duplicates = 0
        self.database_errors = 0
        self.query_errors = 0
        self.write_latencies_ms: list[float] = []
        self.query_latencies_ms: list[float] = []
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"cse3069_concurrent_{name}_{int(time.time())}",
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            return
        client.subscribe(MQTT_TOPIC, qos=1)
        self.connected.set()

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        received_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        raw_payload = message.payload.decode("utf-8", errors="replace")
        with self.lock:
            self.total_received += 1

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            with self.lock:
                self.rejected += 1
            return

        validation = validate_payload(payload)
        if not validation.accepted:
            with self.lock:
                self.rejected += 1
            return

        started = time.perf_counter()
        try:
            inserted = self.database.insert_telemetry(
                payload, validation.quality_status, received_at, raw_payload
            )
        except Exception:
            with self.lock:
                self.database_errors += 1
            return
        latency_ms = (time.perf_counter() - started) * 1000

        with self.lock:
            self.write_latencies_ms.append(latency_ms)
            if inserted:
                self.stored += 1
            else:
                self.duplicates += 1

    def _query_worker(self) -> None:
        connection = sqlite3.connect(DATABASE_PATH, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        query = """
            SELECT device_id, COUNT(*), AVG(temperature), AVG(humidity),
                   MIN(temperature), MAX(temperature)
            FROM telemetry
            GROUP BY device_id
        """
        try:
            while not self.stop_queries.is_set():
                started = time.perf_counter()
                try:
                    connection.execute(query).fetchall()
                    latency_ms = (time.perf_counter() - started) * 1000
                    with self.lock:
                        self.query_latencies_ms.append(latency_ms)
                except sqlite3.Error:
                    with self.lock:
                        self.query_errors += 1
        finally:
            connection.close()

    @staticmethod
    def _p95(values: list[float]) -> float:
        return float(np.percentile(values, 95)) if values else 0.0

    def run(self) -> ExperimentResult:
        query_thread: threading.Thread | None = None
        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        if not self.connected.wait(timeout=5):
            self.client.loop_stop()
            self.database.close()
            raise RuntimeError(f"{self.name}: could not connect and subscribe to MQTT")

        if self.heavy_queries:
            query_thread = threading.Thread(target=self._query_worker, daemon=True)
            query_thread.start()

        print(
            f"Running {self.name} for {self.duration_seconds:.0f}s "
            f"(heavy_queries={self.heavy_queries})..."
        )
        time.sleep(self.duration_seconds)

        self.stop_queries.set()
        if query_thread is not None:
            query_thread.join(timeout=5)
        self.client.disconnect()
        self.client.loop_stop()
        self.database.close()

        with self.lock:
            return ExperimentResult(
                experiment=self.name,
                duration_seconds=self.duration_seconds,
                total_received=self.total_received,
                stored_successfully=self.stored,
                rejected=self.rejected,
                duplicates=self.duplicates,
                database_errors=self.database_errors,
                avg_write_latency_ms=(
                    statistics.fmean(self.write_latencies_ms)
                    if self.write_latencies_ms
                    else 0.0
                ),
                p95_write_latency_ms=self._p95(self.write_latencies_ms),
                query_count=len(self.query_latencies_ms),
                query_errors=self.query_errors,
                avg_query_latency_ms=(
                    statistics.fmean(self.query_latencies_ms)
                    if self.query_latencies_ms
                    else 0.0
                ),
                p95_query_latency_ms=self._p95(self.query_latencies_ms),
            )


def write_csv(results: list[ExperimentResult]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(results[0]).keys())
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            for key, value in row.items():
                if isinstance(value, float):
                    row[key] = f"{value:.6f}"
            writer.writerow(row)


def write_chart(results: list[ExperimentResult]) -> None:
    labels = [result.experiment for result in results]
    averages = [result.avg_write_latency_ms for result in results]
    p95_values = [result.p95_write_latency_ms for result in results]
    positions = np.arange(len(labels))
    width = 0.36

    figure, axis = plt.subplots(figsize=(9, 5))
    axis.bar(positions - width / 2, averages, width, label="Average")
    axis.bar(positions + width / 2, p95_values, width, label="P95")
    axis.set_ylabel("SQLite write latency (ms)")
    axis.set_title("Concurrent Query Impact on Telemetry Writes")
    axis.set_xticks(positions, labels)
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(CHART_PATH, dpi=150, bbox_inches="tight")
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="Duration of each experiment in seconds (default: 20)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.duration < 6:
        raise SystemExit("--duration must be at least 6 seconds")

    results = [
        Experiment("A_no_heavy_query", args.duration, False).run(),
        Experiment("B_with_heavy_query", args.duration, True).run(),
    ]
    write_csv(results)
    write_chart(results)

    for result in results:
        print(json.dumps(asdict(result), indent=2))
    print(f"CSV: {CSV_PATH}")
    print(f"Chart: {CHART_PATH}")


if __name__ == "__main__":
    main()

