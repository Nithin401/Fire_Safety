# FireShield AI — Open Questions & Decision Log

This document records technical, hardware, and operational assumptions made during development to keep engineering moving without blocking on human decisions.

| ID | Topic | Decision / Assumption Adopted | Rationale | Revisit When |
|---|---|---|---|---|
| **OQ-01** | Multi-Sensor Microcontroller Platform | **Recommend ESP32** for multi-sensor node, while maintaining ESP8266 compatibility code. | ESP8266 has only 1 ADC channel (`A0`), insufficient for simultaneous analog flame and MQ-2/MQ-135 smoke sensing without an external multiplexer. | Hardware procurement for pilot build. |
| **OQ-02** | Alert Notification Channel | Primary: **FCM (Firebase Cloud Messaging)**. Secondary: **Server-side Telegram Bot**. | Guarantees background push delivery to mobile without holding open WebSocket connections; Telegram provides ops telemetry. | Pilot customer notification requirements finalized. |
| **OQ-03** | Suppression Actuation Authority | **Deterministic Rule Engine with Persistence Confirmation** is the hard safety backstop. | Machine learning models serve in an advisory, early-warning, and false-alarm suppression capacity. Autonomous suppression must never be solely delegated to black-box ML. | Safety compliance review (UL/NFPA). |
| **OQ-04** | Cloud Hosting Target | **Google Cloud Run + Firebase Firestore**. | Containerized serverless architecture minimizes prototype cost, auto-scales to zero, and integrates natively with Firestore and FCM. | Beta pilot scaling. |
