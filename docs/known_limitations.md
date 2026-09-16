# FireShield AI — Known System Limitations & Technical Disclosures

**Date:** September 2026  
**Audience:** Founders, Technical Advisors, Investors, Certification Engineers  

---

## 1. What Is Software-Verified & Simulated Today
1. **Machine Learning Model Weights (`ml/models/v1/model.pkl`, `model.onnx`)**:
   - The current model achieved 100% test accuracy on multi-channel synthetic stochastic datasets (`data/processed/v1/dataset.parquet`).
   - **Limitation**: Real-world chemical aerosols (cooking vapors, tobacco, e-cigarettes) and sensor degradation (soot buildup on photodiode lens) may introduce distribution shifts.
   - **Remediation**: Retraining must occur as real sensor data is captured during physical pilot deployment according to `docs/ml_retraining_policy.md`.
2. **Firmware Execution in Wokwi & Desktop Harness**:
   - All C/C++ algorithms (moving-median baseline, persistence counters, angle mapping, packet XOR checksums, failsafe watchdog) have been verified via native unit tests and Wokwi simulation.
   - **Limitation**: Physical electromagnetic interference (EMI) from high-current DC motor/pump switching may cause ESP-NOW radio retries or 3.3V power rail ripple on breadboards.
   - **Remediation**: Production PCBs must incorporate flyback diodes across relay coils and 100 µF + 100 nF decoupling capacitors across sensor rails.
3. **Response Actuator (Suppression Discharge)**:
   - Evaluated using low-voltage DC water pump relay simulation.
   - **Limitation**: This prototype is **not certified** for commercial fire suppression or mains electricity (120V/230V). Water spray must never be directed at energized electrical appliances.

---

## 2. What Is Production-Ready & Tested Today
1. **Decoupled Architecture**: Edge nodes make independent safety decisions even when internet is severed.
2. **Binary Packet Mesh Contract**: Rigid, packed binary struct with XOR checksums and strict angle validation (`firmware/include/packet_contract.h`).
3. **Hardened Cloud Backend & Firestore Bridge**: Dockerized Flask service with API key authentication, live hybrid ML risk scoring, rate-limited alerts, and audit trail logging.
4. **Ops Fleet Dashboard**: Real-time browser-based monitoring console (`tools/ops_dashboard/index.html`) with interactive test injection.
5. **Mobile Application**: Clean Flutter codebase (`D:\FireShieldAI`) with zero analyzer errors, streaming live telemetry and rendering dynamic directional radar indicators.
