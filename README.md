# Smart Fire Detection & Response

An engineering prototype for local ESP32 fire-risk detection that can later report to FireShield AI. It is **not** a certified fire alarm, fire detector, or suppression controller.

## What works in this milestone

- Wokwi ESP32 simulation with DHT22 temperature/humidity input on GPIO 4.
- Local temperature trend, baseline, moving filter, and persistence confirmation.
- `SAFE`, `WARNING`, `HIGH_RISK`, and `FIRE` states using configurable **prototype thresholds requiring experimental validation**.
- OLED, LED, and buzzer local-status interface that does not depend on Wi-Fi.
- Human-readable Serial Monitor output plus CSV- and JSON-formatted telemetry records.
- A clearly labelled synthetic dataset for pipeline testing only.

## Run in Wokwi

1. Open this folder in VS Code with PlatformIO and the Wokwi extension installed.
2. Build the `esp32dev` environment.
3. Start Wokwi using [diagram.json](diagram.json).
4. Open Serial Monitor at `115200` baud.
5. Change the DHT22 temperature in the simulator and keep it high long enough for the 10-second persistence confirmation. The joystick is a stand-in for an MQ-2 analog level; the red button simulates a flame sensor input.

## Hardware map

| Function | ESP32 pin | Prototype note |
|---|---:|---|
| DHT22 data (simulation) | GPIO 4 | Physical system uses BME280, not DHT22 |
| MQ-2 analogue signal | GPIO 34 | Input-only; use a voltage divider/level shifter for any 5 V module output |
| Flame sensor digital signal | GPIO 27 | Confirm module voltage and active logic |
| OLED I2C SDA/SCL | GPIO 21 / GPIO 22 | 0.96-inch SSD1306 display |
| Buzzer | GPIO 25 | Low-voltage prototype only |
| Green/red status LEDs | GPIO 16 / GPIO 17 | Local state indication |

## FireShield AI connection

The existing platform accepts MQTT at `fireshield/v1/devices/{deviceId}/telemetry` and REST at `POST /v1/telemetry`. Firmware currently emits compatible **serial JSON** as the safe first step. Before enabling Wi-Fi transport, register the device and room in FireShield and populate every required platform field (including battery, signal strength, smoke, CO, and CO2) only with genuine measurements or clearly labelled adapter values.

See [alert-and-message design](docs/alerts_and_messages.md) for the alert flow and [test plan](docs/testing.md) for acceptance checks.

## Safety boundary

Do not conduct uncontrolled fire tests. Do not connect response hardware to mains electricity. Do not treat water as safe around energized electrical equipment. Validate sensing, false-alarm behavior, messaging reliability, and emergency procedures with qualified fire-safety professionals before any real deployment.
