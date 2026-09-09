#include <Arduino.h>
#include <DHT.h>
#include "communication/telemetry.h"
#include "config.h"
#include "detection/temperature_detector.h"
#include "interface/local_alert.h"
#include "pin_config.h"

namespace {
DHT dht(pins::DHT_DATA, DHT22);
TemperatureDetector detector;
LocalAlert localAlert;
Telemetry telemetry;
unsigned long lastSample = 0;
}

const char* statusName(FireStatus status) {
  switch (status) { case FireStatus::SAFE: return "SAFE"; case FireStatus::WARNING: return "WARNING"; case FireStatus::HIGH_RISK: return "HIGH_RISK"; case FireStatus::FIRE: return "FIRE"; }
  return "UNKNOWN";
}

void setup() {
  Serial.begin(115200); dht.begin(); pinMode(pins::MQ2_ANALOG, INPUT); pinMode(pins::FLAME_DIGITAL, INPUT_PULLUP);
  localAlert.begin(); telemetry.begin();
  Serial.println("Prototype thresholds require experimental validation.");
}

void loop() {
  telemetry.maintainConnection();
  const unsigned long now = millis();
  if (now - lastSample < config::SAMPLE_INTERVAL_MS) return;
  lastSample = now;
  SensorReadings readings;
  readings.temperatureC = dht.readTemperature(); readings.humidityPercent = dht.readHumidity();
  readings.gasRaw = analogRead(pins::MQ2_ANALOG); readings.flameDetected = digitalRead(pins::FLAME_DIGITAL) == LOW;
  readings.valid = !isnan(readings.temperatureC) && !isnan(readings.humidityPercent);
  if (!readings.valid) { Serial.println("Sensor error: DHT22 read failed"); return; }
  const RiskAssessment assessment = detector.update(readings.temperatureC, now);
  localAlert.render(readings, assessment); telemetry.publishSerial(readings, assessment); telemetry.publishMqtt(readings, assessment);
}
