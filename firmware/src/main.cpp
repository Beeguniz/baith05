#include <Arduino.h>
#include <ArduinoMqttClient.h>
#include <DHT.h>
#include <WiFi.h>
#include <esp_system.h>

#include "app_config.h"
#include "wifi_manager.h"

namespace {

constexpr uint8_t DHT_SENSOR_TYPE = DHT11;
DHT dht(AppConfig::DHT_DATA_PIN, DHT_SENSOR_TYPE);
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

unsigned long lastReadAtMs = 0;
unsigned long lastMqttAttemptAtMs = 0;
uint32_t readingSequence = 0;
char bootId[25] = {};

void createBootId() {
  const uint64_t chipId = ESP.getEfuseMac();
  const uint32_t randomPart = esp_random();
  snprintf(bootId, sizeof(bootId), "%08lX%08lX",
           static_cast<unsigned long>(chipId & 0xFFFFFFFFULL),
           static_cast<unsigned long>(randomPart));
}

void updateMqttConnection() {
  if (!WifiManager::isConnected()) {
    if (mqttClient.connected()) {
      mqttClient.stop();
    }
    return;
  }

  if (mqttClient.connected()) {
    mqttClient.poll();
    return;
  }

  const unsigned long nowMs = millis();
  if (nowMs - lastMqttAttemptAtMs < AppConfig::MQTT_RETRY_INTERVAL_MS) {
    return;
  }
  lastMqttAttemptAtMs = nowMs;

  Serial.printf("[MQTT] Connecting to %s:%u...\n", AppConfig::MQTT_BROKER,
                AppConfig::MQTT_PORT);
  mqttClient.setId((String(AppConfig::DEVICE_ID) + "_" + bootId).c_str());

  if (mqttClient.connect(AppConfig::MQTT_BROKER, AppConfig::MQTT_PORT)) {
    Serial.println("[MQTT] Connected");
  } else {
    Serial.printf("[MQTT] Connection failed. Error: %d\n",
                  mqttClient.connectError());
  }
}

bool publishTelemetry(float temperatureC, float humidity, bool valid,
                      uint32_t sequence, unsigned long uptimeMs) {
  if (!mqttClient.connected()) {
    Serial.println("[MQTT] Publish skipped: broker not connected");
    return false;
  }

  String payload;
  payload.reserve(256);
  payload += "{\"device_id\":\"";
  payload += AppConfig::DEVICE_ID;
  payload += "\",\"boot_id\":\"";
  payload += bootId;
  payload += "\",\"seq\":";
  payload += sequence;
  payload += ",\"ts\":";
  payload += uptimeMs;
  payload += ",\"ts_unit\":\"uptime_ms\",\"temperature\":";

  if (valid) {
    payload += String(temperatureC, 1);
    payload += ",\"humidity\":";
    payload += String(humidity, 1);
  } else {
    payload += "null,\"humidity\":null";
  }

  payload += ",\"temperature_unit\":\"C\",\"humidity_unit\":\"%\",\"valid\":";
  payload += valid ? "true}" : "false}";

  // ArduinoMqttClient parameters: topic, payload length, retained, QoS.
  mqttClient.beginMessage(AppConfig::MQTT_TOPIC, payload.length(), false, 1);
  mqttClient.print(payload);
  const int result = mqttClient.endMessage();

  if (result == 1) {
    Serial.printf("[MQTT] Published QoS1: %s\n", payload.c_str());
    return true;
  }

  Serial.printf("[MQTT] Publish failed. Error: %d\n", result);
  return false;
}

void printSensorReading() {
  const float humidity = dht.readHumidity();
  const float temperatureC = dht.readTemperature();
  const unsigned long uptimeMs = millis();

  ++readingSequence;

  Serial.printf("[DHT11] seq=%lu uptime_ms=%lu ",
                static_cast<unsigned long>(readingSequence), uptimeMs);

  if (isnan(humidity) || isnan(temperatureC)) {
    Serial.println("valid=false error=READ_FAILED");
    publishTelemetry(0.0F, 0.0F, false, readingSequence, uptimeMs);
    return;
  }

  Serial.printf("valid=true temperature=%.1f C humidity=%.1f %%\n",
                temperatureC, humidity);
  publishTelemetry(temperatureC, humidity, true, readingSequence, uptimeMs);
}

}  // namespace

void setup() {
  Serial.begin(AppConfig::SERIAL_BAUD_RATE);
  delay(1000);

  Serial.println();
  Serial.println("CSE3069_TH05 - Phase 3: ESP32 + DHT11 + MQTT");
  Serial.printf("DHT11 data pin: GPIO%u\n", AppConfig::DHT_DATA_PIN);
  createBootId();
  Serial.printf("Boot ID: %s\n", bootId);
  Serial.println("Initializing sensor...");

  dht.begin();
  WifiManager::begin();

  // Warm up the sensor. Network connections continue asynchronously in loop().
  delay(2000);
  lastReadAtMs = millis();
}

void loop() {
  WifiManager::update();
  updateMqttConnection();

  const unsigned long nowMs = millis();

  // Subtraction remains correct when millis() wraps around.
  if (nowMs - lastReadAtMs >= AppConfig::SENSOR_READ_INTERVAL_MS) {
    lastReadAtMs = nowMs;
    printSensorReading();
  }
}

