"""Central configuration for the phase 4 MQTT ingestion service."""

import os

MQTT_HOST = os.getenv("CSE3069_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("CSE3069_MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv(
    "CSE3069_MQTT_TOPIC", "cse3069/th05/esp32/telemetry"
)
MQTT_QOS = 1
CLIENT_ID = os.getenv("CSE3069_INGEST_CLIENT_ID", "cse3069_th05_ingest")


