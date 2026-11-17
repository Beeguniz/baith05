CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY,
    device_id TEXT NOT NULL,
    boot_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    device_ts_ms INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    temperature REAL NULL,
    humidity REAL NULL,
    temperature_unit TEXT,
    humidity_unit TEXT,
    valid INTEGER NOT NULL CHECK (valid IN (0, 1)),
    quality_status TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    UNIQUE (device_id, boot_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_id
    ON telemetry (device_id);

CREATE INDEX IF NOT EXISTS idx_telemetry_received_at
    ON telemetry (received_at);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_received_at
    ON telemetry (device_id, received_at);

