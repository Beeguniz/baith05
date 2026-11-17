"""Create temperature and humidity charts from real SQLite telemetry."""

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "greenhouse.db"
RESULTS_DIR = PROJECT_ROOT / "results"
LOCAL_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def normalize_time(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("time must include +07:00 or Z")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def load_data(device_id: str, start: str, end: str) -> pd.DataFrame:
    query = """
        SELECT id, device_id, boot_id, seq, device_ts_ms, received_at,
               temperature, humidity, temperature_unit, humidity_unit,
               valid, quality_status
        FROM telemetry
        WHERE device_id = ?
          AND received_at >= ?
          AND received_at <= ?
        ORDER BY received_at ASC
    """
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA busy_timeout = 5000")
        frame = pd.read_sql_query(query, connection, params=(device_id, start, end))

    if not frame.empty:
        frame["received_at"] = pd.to_datetime(frame["received_at"], utc=True)
        frame["received_at_local"] = frame["received_at"].dt.tz_convert(LOCAL_TIMEZONE)
    return frame


def plot_measurement(
    frame: pd.DataFrame,
    column: str,
    unit: str,
    title: str,
    output_path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(12, 6))

    normal = frame[
        frame["quality_status"].eq("VALID") & frame[column].notna()
    ]
    suspect = frame[
        frame["quality_status"].eq("SUSPECT") & frame[column].notna()
    ]
    invalid = frame[
        frame["quality_status"].eq("INVALID_SENSOR")
    ]

    if not normal.empty:
        axis.plot(
            normal["received_at_local"],
            normal[column],
            color="#1976d2" if column == "temperature" else "#00897b",
            marker="o",
            markersize=4,
            linewidth=1.5,
            label="Valid",
        )

    if not suspect.empty:
        axis.scatter(
            suspect["received_at_local"],
            suspect[column],
            color="#ef6c00",
            marker="^",
            s=70,
            label="Suspect",
            zorder=3,
        )

    # Invalid sensor reads have NULL measurements and must not be converted to
    # zero. Mark their receive times along the bottom of the axes instead.
    if not invalid.empty:
        axis.scatter(
            invalid["received_at_local"],
            [0.02] * len(invalid),
            transform=axis.get_xaxis_transform(),
            color="#c62828",
            marker="x",
            s=60,
            label="Invalid sensor (NULL)",
            zorder=4,
        )

    axis.set_title(title)
    axis.set_xlabel("Received time (Asia/Ho_Chi_Minh)")
    axis.set_ylabel(f"{column.replace('_', ' ').title()} ({unit})")
    axis.grid(True, alpha=0.25)
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=LOCAL_TIMEZONE))
    fig.autofmt_xdate()

    if not normal.empty or not suspect.empty or not invalid.empty:
        axis.legend()
    else:
        axis.text(
            0.5,
            0.5,
            "No measurements in selected range",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", default="esp32_dht11")
    parser.add_argument("--start", help="ISO-8601 start time, inclusive")
    parser.add_argument("--end", help="ISO-8601 end time, inclusive")
    parser.add_argument("--last-hours", type=float, default=1.0)
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

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_data(args.device_id, start, end)

    csv_path = RESULTS_DIR / "telemetry_export.csv"
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    plot_measurement(
        frame,
        "temperature",
        "°C",
        f"ESP32 DHT11 Temperature - {args.device_id}",
        RESULTS_DIR / "chart_temperature.png",
    )
    plot_measurement(
        frame,
        "humidity",
        "%",
        f"ESP32 DHT11 Humidity - {args.device_id}",
        RESULTS_DIR / "chart_humidity.png",
    )

    print(f"device_id={args.device_id} start={start} end={end} rows={len(frame)}")
    print(f"valid={int(frame['quality_status'].eq('VALID').sum()) if not frame.empty else 0}")
    print(f"suspect={int(frame['quality_status'].eq('SUSPECT').sum()) if not frame.empty else 0}")
    print(
        f"invalid_sensor={int(frame['quality_status'].eq('INVALID_SENSOR').sum()) if not frame.empty else 0}"
    )
    print(f"CSV: {csv_path}")
    print(f"Temperature chart: {RESULTS_DIR / 'chart_temperature.png'}")
    print(f"Humidity chart: {RESULTS_DIR / 'chart_humidity.png'}")


if __name__ == "__main__":
    main()

