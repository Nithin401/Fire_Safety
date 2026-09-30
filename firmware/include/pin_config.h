#pragma once

// Central GPIO map. Do not scatter ESP32 pin numbers through source files.
namespace pins {
constexpr int DHT_DATA = 4;       // Simulation only; physical prototype uses BME280 over I2C.
constexpr int MQ2_ANALOG = 34;    // Input-only. Never expose ESP32 ADC to more than 3.3 V.
constexpr int FLAME_DIGITAL = 27;
constexpr int OLED_SDA = 21;
constexpr int OLED_SCL = 22;
constexpr int BUZZER = 25;
constexpr int SAFE_LED = 16;
constexpr int ALERT_LED = 17;
}
