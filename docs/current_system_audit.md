# Current System Audit

**Audit Date:** 2026-09-08

## Overview
The Smart Fire Detection & Response System currently consists of a two-node ESP8266 architecture.

### ESP1 (Detection Node)
- **Role**: Senses environmental parameters.
- **Current State**: Being transitioned to a pure data-logging mode for AI development. Currently reading from a single IR Flame Sensor on the Analog pin (`A0`).
- **Communication**: Broadcasts CSV data over Serial for Python collection. (ESP-NOW will be reintroduced after AI models are finalized).

### ESP2 (Response Node)
- **Role**: Aims servo and triggers the extinguisher relay.
- **Current State**: Established firmware exists (`firmware/esp2_response/ESP2_Advanced.ino`).
- **Safety**: DRY_RUN mode recommended during software testing. DO NOT connect high-voltage mains.

### FireShield AI
- **Role**: Existing Flutter/Node/Postgres application located at `D:\FireShieldAI`.
- **Status**: Retained and unmodified. Future integration will pipe ESP1 risk-scores to FireShield AI over WiFi/MQTT.

## Limitations
- This is a non-certified, experimental prototype.
- Thresholds and logic are purely rule-based at this stage.
- Real machine learning will only be activated after sufficient real-world data is collected.
