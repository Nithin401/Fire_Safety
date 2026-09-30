#include <Arduino.h>
#include "config.h"

unsigned long lastSampleTime = 0;

void setup() {
  Serial.begin(115200);
  delay(100);

  // Print initial CSV header
  Serial.println("timestamp_ms,device_id,room_id,flame_raw");
}

void loop() {
  unsigned long currentTime = millis();

  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = currentTime;

    // Read analog value from flame sensor
    int flameRaw = analogRead(FLAME_SENSOR_PIN);

    // Output strictly machine-readable CSV format
    Serial.print(currentTime);
    Serial.print(",");
    Serial.print(DEVICE_ID);
    Serial.print(",");
    Serial.print(ROOM_ID);
    Serial.print(",");
    Serial.println(flameRaw);
  }
}
