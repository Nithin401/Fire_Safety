# Wokwi to FireShield MQTT

## What is connected

The firmware publishes to the FireShield MQTT topic:

```text
fireshield/v1/devices/esp32-room-1/telemetry
```

FireShield's API subscribes to that topic, validates the incoming message, runs its risk engine, stores the reading and alert, then makes it visible in the mobile dashboard and Alerts screen.

## Required local services

1. Start FireShield from its source folder:

   ```powershell
   docker compose up -d
   ```

2. In VS Code, open this `Fire_Safety` folder and start the Wokwi simulation. Wokwi for VS Code includes the private IoT gateway needed for `host.wokwi.internal` to reach the local Mosquitto broker.
3. Keep the Wokwi simulator tab visible: paused simulations do not publish telemetry.
4. Open `http://localhost:3000/v1/devices/esp32-room-1/latest` to verify the live Wokwi reading.

## Simulation boundary

`dataSource` is explicitly sent as `WOKWI_SIMULATION_NOT_REAL_EXPERIMENTAL_DATA`. The MQ-2 joystick value is sent as simulated `smoke`; `co`, `co2`, battery, and signal strength are placeholder simulation fields required by the present FireShield contract. They are not physical measurements and must be replaced by genuine supported sensor data before any real-world use.

## Triggering an app alert

Set the Wokwi DHT22 to a sustained high temperature and leave the simulation running. FireShield's existing risk service assesses each telemetry record independently and will create an alert when its configured risk score crosses its alert level. These are prototype rules, not validated fire thresholds.

## If MQTT does not connect

- Confirm Docker is running and port `1883` is available locally.
- Run Wokwi from VS Code with its private IoT gateway enabled; browser-only/public Wokwi cannot reach `host.wokwi.internal`.
- Look for `MQTT telemetry published to FireShield` in the Serial Monitor.
- For a physical ESP32, replace `Wokwi-GUEST` and `host.wokwi.internal` with the real Wi-Fi and broker values, using secrets outside source control.
