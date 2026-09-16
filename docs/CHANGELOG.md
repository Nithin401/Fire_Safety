# FireShield AI — Engineering Changelog

All notable changes, milestone progressions, and implementation notes are documented in this file.

## [2026-09-16] — Project Kickoff & Security Hardening
- **Security**:
  - Validated zero exposed active credentials across repository.
  - Added `.gitignore` ignoring `.env`, `serviceAccountKey.json`, and build caches.
  - Created `.env.example` defining template configuration for backend, Firestore, and alert dispatchers.
- **Tracking**:
  - Integrated `FireShieldAI_Milestone_Submission_Updated.xlsx` into version control.
  - Initialized `docs/OPEN_QUESTIONS.md` for assumption logging.

## [2026-09-16] — Milestone M1: Basic Fire Detection & Automated Response
- **Firmware & Networking**:
  - Formalized unified binary packet contract in `firmware/include/packet_contract.h` with XOR checksums and angle validation.
  - Modularized pure C/C++ detection algorithms (`firmware/include/detection_logic.h`) and response watchdog failsafe (`firmware/include/response_logic.h`).
  - Implemented unit tests in `tests/test_firmware_logic.py` passing 100% on desktop without physical hardware dependency.
  - Authored physical verification protocol and interim Wokwi simulation guide in `docs/test_protocol_m1.md`.
  - Updated `FireShieldAI_Milestone_Submission_Updated.xlsx` status for M1 to **Completed**.
