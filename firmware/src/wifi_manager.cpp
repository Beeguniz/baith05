#include "wifi_manager.h"

#include <WiFi.h>

#include "app_config.h"
#include "secrets.h"

namespace WifiManager {
namespace {

unsigned long lastAttemptAtMs = 0;
wl_status_t lastStatus = WL_NO_SHIELD;

void startConnection() {
  Serial.printf("[WiFi] Connecting to SSID: %s\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastAttemptAtMs = millis();
}

}  // namespace

void begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  startConnection();
}

void update() {
  const wl_status_t status = WiFi.status();

  if (status != lastStatus) {
    if (status == WL_CONNECTED) {
      Serial.printf("[WiFi] Connected. IP: %s, RSSI: %d dBm\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else if (lastStatus == WL_CONNECTED) {
      Serial.printf("[WiFi] Disconnected. Status: %d\n", status);
    }
    lastStatus = status;
  }

  if (status != WL_CONNECTED &&
      millis() - lastAttemptAtMs >= AppConfig::WIFI_RETRY_INTERVAL_MS) {
    WiFi.disconnect();
    startConnection();
  }
}

bool isConnected() {
  return WiFi.status() == WL_CONNECTED;
}

}  // namespace WifiManager

