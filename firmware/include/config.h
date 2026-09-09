#pragma once

namespace config {
constexpr char DEVICE_ID[] = "esp32-room-1";
constexpr char ROOM_ID[] = "ROOM_1";
constexpr unsigned long SAMPLE_INTERVAL_MS = 2000;
constexpr unsigned long CONFIRMATION_DURATION_MS = 10000;
constexpr float EMA_ALPHA = 0.25F;

// Wokwi VS Code uses its private gateway to reach this local Docker broker.
// Change only these values for a real ESP32 deployment; never commit Wi-Fi secrets.
constexpr char WIFI_SSID[] = "Wokwi-GUEST";
constexpr char WIFI_PASSWORD[] = "";
constexpr char MQTT_HOST[] = "host.wokwi.internal";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_TOPIC_PREFIX[] = "fireshield/v1/devices/";
constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 5000;

// PROTOTYPE THRESHOLDS REQUIRING EXPERIMENTAL VALIDATION.
constexpr float WARNING_TEMPERATURE_C = 40.0F;
constexpr float HIGH_RISK_TEMPERATURE_C = 55.0F;
constexpr float FIRE_TEMPERATURE_C = 70.0F;
constexpr float WARNING_RATE_C_PER_MIN = 3.0F;
constexpr float HIGH_RISK_RATE_C_PER_MIN = 8.0F;
constexpr float FIRE_RATE_C_PER_MIN = 15.0F;
}
