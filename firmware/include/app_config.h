#pragma once

#include <Arduino.h>

namespace AppConfig {

// Change this value if the DHT11 DATA wire is connected to another GPIO.
constexpr uint8_t DHT_DATA_PIN = 4;

// DHT11 should not be sampled faster than once per second. Two seconds is
// conservative and keeps the serial output easy to inspect.
constexpr unsigned long SENSOR_READ_INTERVAL_MS = 2000;

constexpr unsigned long SERIAL_BAUD_RATE = 115200;

constexpr char DEVICE_ID[] = "esp32_dht11";
constexpr char MQTT_BROKER[] = "192.168.1.215";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_TOPIC[] = "cse3069/th05/esp32/telemetry";

constexpr unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 5000;

}  // namespace AppConfig


