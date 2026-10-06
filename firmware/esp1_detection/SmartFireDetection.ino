/* =====================================================================
   FIRESHIELD AI — SMART FIRE DETECTION & TELEMETRY SYSTEM
   MASTER ESP1 HARDWARE FIRMWARE (ESP8266)
   =====================================================================
   Platform: ESP8266 (NodeMCU 1.0 / WeMos D1 Mini / ESP-12E)
   Architecture: Real-time Multi-Sensor Fusion + Firebase RTDB + ESP-NOW
   
   SENSORS & ACTUATORS (TARGET PIN ARCHITECTURE):
     - BME280 (I2C 0x76 or 0x77): Ambient Temperature, Humidity, Pressure
     - ADS1115 (I2C 0x48):
         * Channel A0: KY-026 Flame Sensor (Analog AO)
         * Channel A1: MQ-2 Gas/Smoke Sensor (Analog AO via 10k/15k divider)
         * Channel A2: Reserved
         * Channel A3: Reserved
     - SG90 Servo (GPIO14 / D5): 0° to 180° directional scanning & fire lock-on
     - ESP-NOW: Fast peer-to-peer radio link to ESP2 Extinguisher Node
     - Firebase Realtime Database: 1 Hz telemetry upload to /devices/ESP1/readings
   ===================================================================== */

#include "ESP1_SmartFireDetection_Firmware.ino"
