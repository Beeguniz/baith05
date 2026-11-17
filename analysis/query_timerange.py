"""Query stored telemetry by device and received-at time range."""

import argparse
import csv
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "greenhouse.db"


def normalize_time(value: str) -> str:
    """Validate ISO-8601 input and normalize it to UTC with a Z suffix."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("time must include a timezone, for example +07:00 or Z")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def query_rows(
    device_id: str,
    start: str,
    end: str,
    database_path: Path = DATABASE_PATH,
) -> tuple[list[str], list[sqlite3.Row]]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM telemetry
            WHERE device_id = ?
              AND received_at >= ?
              AND received_at <= ?
            ORDER BY received_at ASC
            """,
            (device_id, start, end),
        )
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return columns, rows
    finally:
        connection.close()


def export_csv(path: Path, columns: Sequence[str], rows: Sequence[sqlite3.Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(columns)
        writer.writerows(tuple(row) for row in rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", default="esp32_dht11")
    parser.add_argument("--start", help="ISO-8601 start time, inclusive")
    parser.add_argument("--end", help="ISO-8601 end time, inclusive")
    parser.add_argument("--last-hours", type=float, default=1.0)
    parser.add_argument("--csv", type=Path, help="Optional CSV output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if (args.start is None) != (args.end is None):
        raise SystemExit("--start and --end must be provided together")

    if args.start and args.end:
        start = normalize_time(args.start)
        end = normalize_time(args.end)
    else:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=args.last_hours)
        start = start_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        end = end_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    columns, rows = query_rows(args.device_id, start, end)
    print(f"device_id={args.device_id} start={start} end={end} rows={len(rows)}")
    for row in rows:
        print(
            f"{row['received_at']} seq={row['seq']} "
            f"temperature={row['temperature']} humidity={row['humidity']} "
            f"quality={row['quality_status']}"
        )

    if args.csv:
        export_csv(args.csv, columns, rows)
        print(f"CSV exported: {args.csv.resolve()}")


if __name__ == "__main__":
    main()

