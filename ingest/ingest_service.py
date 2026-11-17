"""Phase 4 MQTT consumer: parse, validate, deduplicate and log telemetry."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

import config
from database import TelemetryDatabase
from validator import validate_payload


LOGGER = logging.getLogger("cse3069.ingest")
telemetry_database: TelemetryDatabase | None = None


def on_connect(
    client: mqtt.Client,
    userdata: Any,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code.is_failure:
        LOGGER.error("MQTT connection failed: %s", reason_code)
        return

    LOGGER.info("Connected to MQTT broker %s:%d", config.MQTT_HOST, config.MQTT_PORT)
    client.subscribe(config.MQTT_TOPIC, qos=config.MQTT_QOS)
    LOGGER.info("Subscribed topic=%s qos=%d", config.MQTT_TOPIC, config.MQTT_QOS)


def on_disconnect(
    client: mqtt.Client,
    userdata: Any,
    disconnect_flags: mqtt.DisconnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code != 0:
        LOGGER.warning("Unexpected MQTT disconnect: %s; reconnecting", reason_code)
    else:
        LOGGER.info("Disconnected from MQTT broker")


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    raw_payload = message.payload.decode("utf-8", errors="replace")

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        LOGGER.error("REJECTED invalid_json=%s raw=%r", exc.msg, raw_payload)
        return

    result = validate_payload(payload)
    if not result.accepted:
        LOGGER.error("REJECTED reason=%s raw=%s", result.reason, raw_payload)
        return

    received_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )

    if telemetry_database is None:
        LOGGER.error("Database is not initialized; message was not stored")
        return

    try:
        inserted = telemetry_database.insert_telemetry(
            payload=payload,
            quality_status=result.quality_status,
            received_at=received_at,
            raw_payload=raw_payload,
        )
    except Exception:
        LOGGER.exception("DATABASE_ERROR message was not stored")
        return

    key = (payload["device_id"], payload["boot_id"], payload["seq"])
    if not inserted:
        LOGGER.warning("DUPLICATE key=%s ignored", key)
        return

    LOGGER.info(
        "STORED quality=%s device_id=%s boot_id=%s seq=%s ts=%s received_at=%s "
        "temperature=%s humidity=%s reason=%s",
        result.quality_status,
        payload["device_id"],
        payload["boot_id"],
        payload["seq"],
        payload["ts"],
        received_at,
        payload.get("temperature"),
        payload.get("humidity"),
        result.reason,
    )


def main() -> None:
    global telemetry_database

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    telemetry_database = TelemetryDatabase()
    LOGGER.info("SQLite database=%s", telemetry_database.database_path)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=config.CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    LOGGER.info("Starting ingestion service with SQLite persistence")
    client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)

    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        LOGGER.info("Stopping ingestion service")
        client.disconnect()
    except Exception:
        LOGGER.exception("Fatal ingestion service error")
        sys.exit(1)
    finally:
        telemetry_database.close()
        LOGGER.info("SQLite database closed")


if __name__ == "__main__":
    main()


