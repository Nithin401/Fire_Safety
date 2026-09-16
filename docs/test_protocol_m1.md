# Milestone 1: Test Protocol & Acceptance Report

**Milestone:** M1 — Basic Fire Detection & Automated Response  
**Status:** Software Verified & Desktop Tested | **AWAITING PHYSICAL HARDWARE VALIDATION**  
**Date:** September 2026  

---

## 1. Scope & Objective
Validate the closed-loop autonomous detection and response cycle:
1. **ESP1 Detection Node:** Reads analog flame sensor, applies noise suppression and persistence confirmation, detects flame angle, and serializes packets.
2. **Wireless Comms:** Broadcasts structured ESP-NOW telemetry packets conforming to `firmware/include/packet_contract.h`.
3. **ESP2 Response Node:** Receives packets, verifies checksum and angle validity, maps angle to aim servo, triggers suppression relay (pump), buzzer, and LED.
4. **Failsafe Watchdog:** Ensures immediate automatic cutoff of suppression relay if wireless communication drops for > 3,000 ms.

---

## 2. Hardware Test Protocol (For Physical Deployment)

### Test 1.1: Flame Detection & Thresholding
- **Equipment:** ESP1 node, IR flame sensor module (A0), non-flame heat/optical source (controlled flashlight or IR LED tester).
- **Procedure:**
  1. Power ESP1 with Serial Monitor at 115200 baud.
  2. Observe ambient baseline ADC value (expected: 850–950).
  3. Introduce IR source at 50 cm. Verify ADC drops below threshold (< 400).
  4. Maintain stimulus for >= 3 continuous cycles to confirm persistence counter.
  5. Remove stimulus; verify sensor returns to SAFE baseline.
- **Pass Criteria:** `fire` flag sets to `1` only after persistence confirmation; resets cleanly upon removal.

### Test 1.2: Wireless ESP-NOW Mesh & Checksum Verification
- **Equipment:** ESP1 and ESP2 running with pre-shared MAC addresses on Wi-Fi Channel 6.
- **Procedure:**
  1. Power both nodes.
  2. Transmit `FireDataPacket` across 2.4 GHz ESP-NOW.
  3. Monitor ESP2 serial output for packet arrival, monotonic `packetID`, and checksum validation.
- **Pass Criteria:** 0% packet corruption; invalid checksums rejected without actuation.

### Test 1.3: Response Activation & Directional Targeting
- **Equipment:** ESP2, SG90/MG996R servo, 5V relay module with indicator LED, active buzzer.
- **Procedure:**
  1. Transmit packet with `fire = 1`, `angle = 45`.
  2. Assert servo rotates to 45° (within ±2° tolerance with offset).
  3. Assert relay activates, LED flashes, buzzer sounds alarm.
- **Pass Criteria:** Servo aims accurately; relay switches state within < 200 ms of flame confirmation.

### Test 1.4: Comms Dropout Watchdog Failsafe
- **Procedure:**
  1. Trigger active fire state on ESP2 (relay active).
  2. Cut power to ESP1 or silence transmission.
  3. Start stopwatch.
  4. Assert ESP2 detects timeout at 3,000 ms and shuts down relay, buzzer, and returns servo to 90° center.
- **Pass Criteria:** Relay de-energizes within exactly 3,000–3,100 ms of signal loss.

---

## 3. Interim Wokwi Simulation Verification

In absence of physical hardware on this workstation, the entire logic pipeline was simulated and verified:
- **Wokwi Project:** Configured in `diagram.json` and `wokwi.toml`.
- **Pure Algorithm Unit Tests:** Verified via `pytest tests/test_firmware_logic.py`:
  - `test_packet_contract_serialization_and_validation`: **PASSED**
  - `test_packet_contract_corrupted_checksum`: **PASSED**
  - `test_packet_contract_invalid_angle`: **PASSED**
  - `test_failsafe_watchdog_timeout`: **PASSED**
  - `test_servo_mapping_and_limits`: **PASSED**

---

## 4. Evidence Required for Final Physical Sign-off
1. Photo of dual ESP1 and ESP2 test bench setup with multimeter showing 3.3V and 5V rail stability.
2. Video recording of flame sensor triggering servo aim and relay click.
3. Oscilloscope/logic analyzer trace of ESP-NOW transmission latency.
4. Video demonstrating automatic relay shutoff when ESP1 is abruptly disconnected.
