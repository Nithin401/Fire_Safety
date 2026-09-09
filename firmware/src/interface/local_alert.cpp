#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
#include "local_alert.h"
#include "pin_config.h"

namespace { Adafruit_SSD1306 display(128, 64, &Wire, -1); }

void LocalAlert::begin() {
  pinMode(pins::BUZZER, OUTPUT); pinMode(pins::SAFE_LED, OUTPUT); pinMode(pins::ALERT_LED, OUTPUT);
  Wire.begin(pins::OLED_SDA, pins::OLED_SCL);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C); display.clearDisplay(); display.setTextColor(SSD1306_WHITE);
}

void LocalAlert::render(const SensorReadings& readings, const RiskAssessment& assessment) {
  const bool alarm = assessment.status == FireStatus::HIGH_RISK || assessment.status == FireStatus::FIRE;
  digitalWrite(pins::SAFE_LED, assessment.status == FireStatus::SAFE ? HIGH : LOW);
  digitalWrite(pins::ALERT_LED, alarm ? HIGH : LOW);
  if (alarm) tone(pins::BUZZER, assessment.status == FireStatus::FIRE ? 1800 : 1100, 150); else noTone(pins::BUZZER);
  display.clearDisplay(); display.setTextSize(1); display.setCursor(0, 0);
  display.printf("ROOM: ROOM_1\n%s%s\n", statusName(assessment.status), assessment.confirmed ? "" : " (checking)");
  display.printf("T: %.1f C  H: %.0f %%\n", readings.temperatureC, readings.humidityPercent);
  display.printf("Rate: %.1f C/min\nRisk: %d %%\n", assessment.temperatureRateCPerMin, assessment.riskScore);
  display.printf("Gas: %d Flame: %s", readings.gasRaw, readings.flameDetected ? "YES" : "no");
  display.display();
}
