# FireShield AI — Bill of Materials (BOM) & Unit Economics

**Author:** Technical Co-Founder / Embedded Engineering  
**Date:** September 2026  
**Purpose:** Hardware Cost Model & Investor Unit Economics  

---

## 1. Prototype Unit Bill of Materials (Single Setup: Detection + Response)

| Component | Part / Model | Quantity | Prototype Unit Cost (USD) | Projected Cost @ 100 Units | Projected Cost @ 1,000 Units | Sourcing / Vendor |
|---|---|---:|---:|---:|---:|---|
| **Microcontroller (Detection)** | ESP32-WROOM-32 DevKit V1 | 1 | $3.50 | $2.60 | $1.90 | Espressif / Mouser / LCSC |
| **Microcontroller (Response)** | ESP8266 NodeMCU V3 | 1 | $2.20 | $1.70 | $1.30 | AI-Thinker / LCSC |
| **Flame Sensor (Optical)** | 760–1100 nm IR Photodiode Module (Analog+Digital) | 1 | $1.20 | $0.75 | $0.45 | Waveshare / generic |
| **Combustion Gas Sensor** | MQ-2 / MQ-135 Gas & Smoke Module | 1 | $2.50 | $1.60 | $1.10 | Winsen Sensor / LCSC |
| **Ambient Temp/Humidity** | DHT22 (AM2302) or BME280 | 1 | $3.20 | $2.10 | $1.50 | Aosong / Bosch Sensortec |
| **Targeting Actuator** | MG996R High-Torque Metal Gear Servo (Response) | 1 | $4.80 | $3.20 | $2.40 | TowerPro / OEM |
| **Panning Search Actuator** | SG90 Micro Servo 9g (Detection Sweep) | 1 | $1.60 | $0.95 | $0.65 | TowerPro / OEM |
| **Power Switching** | 5V Optocoupler Relay Module (10A 250VAC) | 1 | $1.50 | $0.90 | $0.60 | Songle / JQC-3FF |
| **Local Status Interface** | 0.96" I2C SSD1306 OLED (128x64) | 1 | $2.80 | $1.80 | $1.30 | Solomon Systech |
| **Audible Alarm & LEDs** | 5V Active Buzzer + Diffused High-Brightness LEDs | 2 | $0.80 | $0.40 | $0.25 | Generic |
| **Extinguisher/Pump (Demo)** | 12V DC Submersible Diaphragm Water Pump / Solenoid | 1 | $8.50 | $5.50 | $3.80 | Generic Industrial / LCSC |
| **Power Supply** | 12V 2A DC Wall Adapter + LM2596 5V Buck Converter | 1 | $6.50 | $4.20 | $2.90 | Mean Well / generic |
| **Enclosure & Custom PCB** | 3D Printed PETG Housing + 2-Layer Custom FR4 PCB | 1 | $12.00 | $6.00 | $3.50 | JLCPCB / PCBWay |
| **Passive Components & Wiring** | Terminal blocks, headers, resistors, silicone wire | 1 | $2.50 | $1.20 | $0.80 | Generic |
| **TOTAL HARDWARE COST (COGS)** | | | **$50.60** | **$32.90** | **$22.45** | |

---

## 2. Unit Margin & Retail Pricing Model

| Metric | Prototype Batch (1–10 units) | Pilot Production (100 units) | Commercial Scale (1,000+ units) |
|---|---:|---:|---:|
| **Hardware COGS** | $50.60 | $32.90 | $22.45 |
| **Assembly & QC Testing** | $15.00 (In-house) | $8.00 (Turnkey EMS) | $4.50 (Contract Manufacturer) |
| **Fully Burdened Unit Cost** | **$65.60** | **$40.90** | **$26.95** |
| **Target Retail Price (Hardware)** | **$199.00** | **$149.00** | **$129.00** |
| **Hardware Gross Margin (%)** | **67.0%** | **72.5%** | **79.1%** |
| **Monthly SaaS Monitoring Fee** | $9.99 / room | $9.99 / room | $9.99 / room |
| **LTV / CAC Ratio (Target)** | N/A (Prototype) | 3.8x | 5.2x |

---

## 3. Key Cost Reduction Insights
1. **PCB Consolidation**: In production, replacing individual breakout modules with SMT components directly on a single ESP32 PCB reduces BOM cost by **38%** and assembly labor by **60%**.
2. **ESP8266 + ESP32 Partitioning**: Using ESP32 strictly where multi-ADC is required, while keeping the low-cost ESP8266 for the secondary response node, preserves unit economics.
