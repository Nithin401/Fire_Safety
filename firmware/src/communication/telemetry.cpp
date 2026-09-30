#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <time.h>
#include "config.h"
#include "telemetry.h"

namespace {
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
unsigned long lastConnectionAttemptMs = 0;

bool currentTimestamp(char* output, size_t outputSize) {
  const time_t now = time(nullptr);
  if (now < 1577836800) return false;  // NTP has not synchronized yet.
  const tm* utc = gmtime(&now);
  return utc != nullptr && strftime(output, outputSize, "%Y-%m-%dT%H:%M:%SZ", utc) > 0;
}

void connectWifi() {
  if (WiFi.status() != WL_CONNECTED) WiFi.begin(config::WIFI_SSID, config::WIFI_PASSWORD, 6);
}
}

void Telemetry::begin() {
  WiFi.mode(WIFI_STA);
  connectWifi();
  mqttClient.setServer(config::MQTT_HOST, config::MQTT_PORT);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

void Telemetry::maintainConnection() {
  if (WiFi.status() != WL_CONNECTED) { connectWifi(); return; }
  if (mqttClient.connected()) { mqttClient.loop(); return; }
  const unsigned long now = millis();
  if (now - lastConnectionAttemptMs < config::MQTT_RETRY_INTERVAL_MS) return;
  lastConnectionAttemptMs = now;
  mqttClient.connect(config::DEVICE_ID);
}

void Telemetry::publishSerial(const SensorReadings& readings, const RiskAssessment& assessment) const {
  Serial.println("========================================");
  Serial.println("SMART FIRE DETECTION SYSTEM");
  Serial.printf("Temperature : %.2f C\nHumidity    : %.2f %%\n", readings.temperatureC, readings.humidityPercent);
  Serial.printf("Temperature Rate : %.2f C/min\nBaseline : %.2f C\n", assessment.temperatureRateCPerMin, assessment.baselineTemperatureC);
  Serial.printf("Fire Risk : %d%%\nStatus    : %s\n", assessment.riskScore, statusName(assessment.status));
  Serial.printf("CSV,%s,%s,%.2f,%.2f,%d,%d,%.2f,%d,%s\n", config::DEVICE_ID, config::ROOM_ID, readings.temperatureC, readings.humidityPercent, readings.gasRaw, readings.flameDetected, assessment.temperatureRateCPerMin, assessment.riskScore, statusName(assessment.status));
  Serial.printf("JSON,{\"deviceId\":\"%s\",\"roomId\":\"%s\",\"temperature\":%.2f,\"humidity\":%.2f,\"gasRaw\":%d,\"flameDetected\":%s,\"temperatureRate\":%.2f,\"riskScore\":%d,\"status\":\"%s\"}\n", config::DEVICE_ID, config::ROOM_ID, readings.temperatureC, readings.humidityPercent, readings.gasRaw, readings.flameDetected ? "true" : "false", assessment.temperatureRateCPerMin, assessment.riskScore, statusName(assessment.status));
  Serial.println("========================================");
}

void Telemetry::publishMqtt(const SensorReadings& readings, const RiskAssessment& assessment) {
  if (!mqttClient.connected()) return;
  char timestamp[25];
  if (!currentTimestamp(timestamp, sizeof(timestamp))) {
    Serial.println("MQTT waiting for NTP time synchronization");
    return;
  }
  char topic[128];
  snprintf(topic, sizeof(topic), "%s%s/telemetry", config::MQTT_TOPIC_PREFIX, config::DEVICE_ID);

  // All values below are labelled simulation values. MQ-2 does not measure CO or CO2 directly.
  // Do not reuse this payload mapping for physical/calibrated hardware.
  char payload[640];
  snprintf(payload, sizeof(payload),
      "{\"deviceId\":\"%s\",\"recordedAt\":\"%s\",\"temperature\":%.2f,\"humidity\":%.2f,\"smoke\":%d,\"co\":0,\"co2\":400,\"battery\":100,\"signalStrength\":-45,\"temperatureRate\":%.2f,\"dataSource\":\"WOKWI_SIMULATION_NOT_REAL_EXPERIMENTAL_DATA\",\"gasRaw\":%d,\"flameDetected\":%s,\"edgeRiskScore\":%d,\"edgeStatus\":\"%s\"}",
      config::DEVICE_ID, timestamp, readings.temperatureC, readings.humidityPercent,
      readings.gasRaw, assessment.temperatureRateCPerMin, readings.gasRaw,
      readings.flameDetected ? "true" : "false", assessment.riskScore, statusName(assessment.status));
  if (mqttClient.publish(topic, payload, false)) Serial.println("MQTT telemetry published to FireShield");
  else Serial.println("MQTT publish failed");
}
