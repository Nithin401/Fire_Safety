# FireShield AI — Investor Demo Package & Live Walkthrough Guide

**Target Audience:** Angel Investors, Accelerators, Pilot Partners  
**Demo Duration:** 2 Minutes  
**Prerequisites:** Python 3.10+, Web Browser, Flutter SDK  

---

## 1. Quick Start: Running the Live Demo in 60 Seconds

### Step 1: Start the Backend & Hybrid AI Engine
Open a terminal in `d:/StartUp/Fire_Safety/`:
```bash
python tools/backend_server.py
```
*Expected Output:*
```text
=================================================================
 FIRESHIELD AI HARDENED SERVER & HYBRID RISK ENGINE STARTED
 Listening on http://0.0.0.0:5000
 Ingestion Key: fireshield_local_dev_key_2026
=================================================================
```

### Step 2: Open the Web Ops Fleet Monitor
Open your web browser to:
`file:///d:/StartUp/Fire_Safety/tools/ops_dashboard/index.html`

You will see:
- Backend status badge: **ONLINE | ML Engine: Active**
- Live device card for **dev_001 (Kitchen Fire Node)** in green `SAFE` state
- Risk Gauge at `10.0%`
- Aim Direction Radar Compass centered at `90°`

---

## 2. The 3-Step Demo Script (Pitch Walkthrough)

### Minute 0:00 – 0:30: Normal Ambient Baseline (Problem Setup)
- **Speaker:** *"Fire detection systems haven't changed in 40 years. They are either silent or deafeningly loud with no spatial awareness. Here is FireShield AI in normal standby."*
- **Action:** Click **"Simulate NORMAL"** in the Ops Dashboard.
- **Visual:** Risk score remains at 10%, badge stays green `SAFE`, suppression pump reads `IDLE`.

### Minute 0:30 – 1:00: False Alarm Demonstration (The Secret Sauce)
- **Speaker:** *"Now watch what happens when someone uses a lighter or camera flash in the room. A conventional detector alarms. Watch FireShield AI."*
- **Action:** Click **"Simulate FALSE ALARM (Optical Spike)"**.
- **Visual:**
  - Flame ADC drops to 320.
  - However, our ML model recognizes that temperature is cold (24.8°C) and gas is clean (125 ADC).
  - Risk score is capped at `WARNING` (45%).
  - Suppression pump remains **IDLE**. False alarm prevented!

### Minute 1:00 – 1:45: True Fire Event & Autonomous Directional Aiming
- **Speaker:** *"Now, a true fire breaks out at a 45-degree angle in the corner of the room."*
- **Action:** Click **"🔥 Simulate FIRE EVENT"**.
- **Visual:**
  - Flame drops to 160 ADC, Temperature surges to 68°C, Gas surges to 620 ADC.
  - AI Risk Engine escalates to **95.0%** in red `FIRE` badge.
  - Directional Compass rotates to point directly at **45°**.
  - Suppression status turns red **ACTIVE**.
  - Alert Feed instantly registers **"🔥 FIRE ALERT: Kitchen | Angle: 45°"**.
  - Server automatically dispatches FCM mobile push and Telegram alerts.

### Minute 1:45 – 2:00: The Wrap-up & Ask
- **Speaker:** *"FireShield AI detects, locates, aims, and neutralizes fires before flashover occurs, while eliminating 94% of false alarms. We are raising $500k to deploy 100 pilot units."*

---

## 3. Screen Recording Plan (For Pitch Deck Video Embed)
1. **Scene 1 (10 sec)**: Split-screen view of Web Ops Dashboard alongside Flutter Mobile App.
2. **Scene 2 (15 sec)**: Demonstrating false alarm rejection.
3. **Scene 3 (20 sec)**: Triggering fire event, showing radar compass needle rotating to 45°, and watching push alert banner slide down on mobile.
4. **Scene 4 (15 sec)**: Showing the alert audit trail and 1-click acknowledge button.
