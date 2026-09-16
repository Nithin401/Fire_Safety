# Hardware Platform Recommendation: ESP8266 vs ESP32 for Multi-Sensor Sensing

**Author:** FireShield AI Embedded Engineering  
**Date:** September 2026  
**Status:** Architecture Recommendation  

---

## 1. Executive Summary
The prototype began on the **ESP8266 (NodeMCU/Wemos D1 Mini)** for both ESP1 (Detection) and ESP2 (Response).
While ESP8266 performs admirably for simple single-sensor or digital applications, **multi-sensor fire detection introduces electrical and peripheral bottlenecks**.

We recommend migrating the primary detection node (ESP1) to **ESP32** for production and pilot deployments, while retaining the lower-cost ESP8266 for the dedicated response node (ESP2).

---

## 2. Technical Comparison

| Specification | ESP8266 (NodeMCU) | ESP32 (NodeMCU / DevKit V1) | Impact on Multi-Sensor Fire System |
|---|---|---|---|
| **ADC Channels** | **1 single channel (`A0`)** | **18 channels** across ADC1 & ADC2 | **CRITICAL**: Cannot read analog Flame + MQ-2 + MQ-135 simultaneously on ESP8266 without an external ADC multiplexer (e.g. ADS1115 or CD74HC4067). ESP32 reads all directly. |
| **ADC Resolution** | 10-bit (0–1023, 0–1.0V) | 12-bit (0–4095, 0–3.3V) | ESP32 provides 4x finer signal resolution for thermal and gas derivative analysis. |
| **I2C / SPI Buses** | 1 software-emulated | 2 dedicated hardware controllers | ESP32 enables simultaneous BME280 environment sensing and SSD1306 OLED without bus lockups. |
| **Processor Cores** | 1 core @ 80/160 MHz | 2 independent cores (Tensilica Xtensa @ 240 MHz) | ESP32 allows Core 0 to handle Wi-Fi/MQTT/ESP-NOW while Core 1 executes strict real-time sensor sampling and ML filtering. |
| **RAM** | ~50 KB usable | ~320 KB SRAM | Essential for rolling window feature buffers (M4) and on-device TinyML inference (M5). |
| **Cost** | ~$1.80 – $2.20 | ~$2.80 – $3.50 | Minimal cost delta (+~$1.00) offset by eliminating the need for an external $1.50 ADC multiplexer chip. |

---

## 3. Alternative Solution: Pin Expansion on ESP8266
If the hardware team must remain on ESP8266 for legacy units, the single `A0` pin must be expanded via:
1. **CD74HC4067 / 74HC4051 Analog Multiplexer**:
   - Uses 3–4 digital GPIOs (e.g., D1, D2, D7) to route channel 0 (Flame) and channel 1 (MQ-2) sequentially into `A0`.
   - Requires settling delay (~50 µs) between channel switching to avoid capacitive ghosting.
2. **ADS1115 I2C 16-Bit 4-Channel ADC**:
   - Offloads all analog readings to I2C bus (`SDA=D2`, `SCL=D1`).
   - Advantage: Extremely accurate, 16-bit resolution, programmable gain amplifier (PGA).

---

## 4. Final Recommendation
1. **ESP1 (Detection Node)**: Migrate to **ESP32**.
   - Pin 4: DHT22 (Temp/Hum) or GPIO 21/22 (I2C BME280)
   - Pin 34: MQ-2 Analog Gas/Smoke
   - Pin 35: Analog Flame IR
   - Pin 27: Digital Flame IR
   - Pin 12: Scan Servo PWM
2. **ESP2 (Response Node)**: Remain on **ESP8266**.
   - ESP2 only needs 1 PWM output (aim servo), 1 relay digital pin, and buzzer/LED pins, which fit comfortably within ESP8266's GPIO footprint.
