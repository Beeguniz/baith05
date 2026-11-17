"""Print SQLite health and storage settings for the project database."""

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "greenhouse.db"


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        print(f"database={DATABASE_PATH}")
        print(f"journal_mode={connection.execute('PRAGMA journal_mode').fetchone()[0]}")
        print(f"synchronous={connection.execute('PRAGMA synchronous').fetchone()[0]}")
        print(f"busy_timeout={connection.execute('PRAGMA busy_timeout').fetchone()[0]}")
        print(f"rows={connection.execute('SELECT count(1) FROM telemetry').fetchone()[0]}")
        indexes = connection.execute("PRAGMA index_list(telemetry)").fetchall()
        print(f"indexes={len(indexes)}")
        print(f"unique_constraint={any(row[2] == 1 for row in indexes)}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

