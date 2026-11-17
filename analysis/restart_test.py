"""Verify committed SQLite telemetry survives an ingestion service restart."""

import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "greenhouse.db"
INGEST_SERVICE = PROJECT_ROOT / "ingest" / "ingest_service.py"
RESULTS_DIR = PROJECT_ROOT / "results"

BEFORE_PATH = RESULTS_DIR / "log_before_restart.txt"
AFTER_PATH = RESULTS_DIR / "log_after_restart.txt"
RESULT_PATH = RESULTS_DIR / "restart_log.txt"
INGEST_BEFORE_LOG = RESULTS_DIR / "restart_ingest_before.log"
INGEST_AFTER_LOG = RESULTS_DIR / "restart_ingest_after.log"

COLLECTION_SECONDS = 10
POST_RESTART_SECONDS = 6


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def start_ingestion(log_path: Path) -> tuple[subprocess.Popen[bytes], Any]:
    log_file = log_path.open("wb")
    process = subprocess.Popen(
        [sys.executable, str(INGEST_SERVICE)],
        cwd=PROJECT_ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return process, log_file


def stop_ingestion(process: subprocess.Popen[bytes], log_file: Any) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log_file.close()


def query_fixed_window(start: str, end: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(DATABASE_PATH, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        rows = connection.execute(
            """
            SELECT id, device_id, boot_id, seq, device_ts_ms, received_at,
                   temperature, humidity, temperature_unit, humidity_unit,
                   valid, quality_status, raw_payload
            FROM telemetry
            WHERE received_at >= ? AND received_at <= ?
            ORDER BY device_id, boot_id, seq, received_at
            """,
            (start, end),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def write_snapshot(path: Path, label: str, start: str, end: str, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(f"snapshot={label}\n")
        output.write(f"T0={start}\n")
        output.write(f"T1={end}\n")
        output.write(f"row_count={len(rows)}\n")
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def row_identity(row: dict[str, Any]) -> tuple[str, str, int]:
    return row["device_id"], row["boot_id"], row["seq"]


def compare_rows(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    differences: list[str] = []
    before_by_key = {row_identity(row): row for row in before}
    after_by_key = {row_identity(row): row for row in after}

    missing = sorted(set(before_by_key) - set(after_by_key))
    added = sorted(set(after_by_key) - set(before_by_key))
    if missing:
        differences.append(f"missing_after_restart={missing}")
    if added:
        differences.append(f"unexpected_in_fixed_window={added}")

    for key in sorted(set(before_by_key) & set(after_by_key)):
        if before_by_key[key] != after_by_key[key]:
            differences.append(f"changed_row={key}")

    return not differences and len(before) == len(after), differences


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Starting ingestion to collect real ESP32 telemetry...")
    t0 = utc_now()
    first_process, first_log = start_ingestion(INGEST_BEFORE_LOG)
    try:
        time.sleep(COLLECTION_SECONDS)
    finally:
        stop_ingestion(first_process, first_log)
    t1 = utc_now()

    before = query_fixed_window(t0, t1)
    write_snapshot(BEFORE_PATH, "before_restart", t0, t1, before)
    if not before:
        message = (
            "FAIL: no real telemetry was stored in the fixed T0-T1 window. "
            "Check ESP32, Mosquitto and ingestion logs."
        )
        RESULT_PATH.write_text(
            f"T0={t0}\nT1={t1}\nbefore_count=0\nresult={message}\n",
            encoding="utf-8",
        )
        raise SystemExit(message)

    print(f"Captured {len(before)} committed rows. Restarting ingestion...")
    second_process, second_log = start_ingestion(INGEST_AFTER_LOG)
    try:
        time.sleep(POST_RESTART_SECONDS)
    finally:
        stop_ingestion(second_process, second_log)

    # Query exactly the original fixed interval. New rows received after T1
    # cannot alter this comparison.
    after = query_fixed_window(t0, t1)
    write_snapshot(AFTER_PATH, "after_restart", t0, t1, after)
    passed, differences = compare_rows(before, after)

    result_lines = [
        f"T0={t0}",
        f"T1={t1}",
        "query_window=fixed",
        f"before_count={len(before)}",
        f"after_count={len(after)}",
        f"keys_equal={set(map(row_identity, before)) == set(map(row_identity, after))}",
        f"values_equal={before == after}",
        f"result={'PASS' if passed else 'FAIL'}",
    ]
    result_lines.extend(differences)
    RESULT_PATH.write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    print("\n".join(result_lines))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

