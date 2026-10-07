# FireShield AI — Master API Keys, Tokens & Credentials Guide

This document centralizes **all API keys, tokens, endpoints, and credentials** used across the Smart Fire Detection System (Hardware Firmware, Firebase Realtime Database, Python Backend/ML, and Flutter Mobile App).

---

## 1. Summary of Credentials & Where to Find Them

| Service / Purpose | Key / Value | Search Location (Console Path) |
| :--- | :--- | :--- |
| **Firebase Project ID** | `smart-fire-detection-272bb` | **Firebase Console** &rarr; Project Settings &rarr; General &rarr; Project ID |
| **Project Number / Sender ID** | `1061002575810` | **Firebase Console** &rarr; Project Settings &rarr; General &rarr; Project number |
| **Realtime Database URL** | `https://smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app` | **Firebase Console** &rarr; Build &rarr; Realtime Database &rarr; Top Data header |
| **Firebase Web API Key** | `AIzaSyCxnGiInekI9FX6f7yUPuwxucYpHrUZWws` | **Firebase Console** &rarr; Project Settings &rarr; General &rarr; Web API Key |
| **Android Firebase API Key** | `AIzaSyBGPqgXRlEnmBRLxxUz-lADNad6fvDNrVk` | **Firebase Console** &rarr; Project Settings &rarr; Your apps &rarr; Android App |
| **iOS/macOS Firebase API Key** | `AIzaSyA6y5NRSU8eE_nYBAToC7ejqKs0Mt7Se5c` | **Firebase Console** &rarr; Project Settings &rarr; Your apps &rarr; iOS App |
| **ESP8266 Auth Email** | `esp1@smartfiredetection.local` | **Firebase Console** &rarr; Build &rarr; Authentication &rarr; Users |
| **ESP8266 Auth Password** | `FS_esp1_Sec#2026_LiveKey!` *(Rotated)* | Set via Firebase Auth REST API (Replaced exposed pass) |
| **ESP8266 Auth UID** | `p5hH921R8EMO5OVL4G6rCsdTf013` | **Firebase Console** &rarr; Build &rarr; Authentication &rarr; User UID |
| **Service Account JSON** | `serviceAccountKey.json` | **Firebase Console** &rarr; Project Settings &rarr; Service Accounts &rarr; Generate key |
| **FCM Cloud Messaging** | Sender: `1061002575810` | **Firebase Console** &rarr; Project Settings &rarr; Cloud Messaging tab |
| **Local Ingestion Key** | `fireshield_local_dev_key_2026` | Configured in root `.env` (`DEVICE_INGESTION_API_KEY`) |

---

## 2. Security Notice & Rotated Credentials

> [!IMPORTANT]
> The previously exposed password (`Esp1SecurePass123`) has been **permanently replaced and rotated** in Firebase Authentication using Google's Identity Toolkit REST API.
> 
> - **Active NodeMCU Password:** `FS_esp1_Sec#2026_LiveKey!`
> - The old password is no longer valid.
> - The active password is saved in `firmware/esp1_detection/secrets.h` and root `.env`, both of which are ignored by Git to prevent leaking to GitHub.

---

## 3. How the Files Connect Together

```text
               ┌──────────────────────────────────────────────┐
               │         ROOT .env / secrets.h                │
               │   (Contains all real active credentials)    │
               │            (IGNORED BY GIT)                  │
               └──────────────┬───────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
[ ESP8266 Firmware ]   [ Python CSV / ML ]   [ Flutter App ]
firmware/esp1_detection/  tools/firebase_to_csv.py  lib/firebase_options.dart
- firebase_config.h     - Reads serviceAccountKey  - Pre-bundled platform
- secrets.h (local)       or REST endpoint         options for Web,
- Connects to RTDB                                Android, iOS, Windows
```

---

## 4. Step-by-Step: How to Find or Regenerate Any Key

### A. If you need the Firebase Web API Key
1. Open [Firebase Console](https://console.firebase.google.com/).
2. Click on **Smart Fire Detection** project.
3. Click the **Gear icon** (top left next to Project Overview) &rarr; **Project settings**.
4. In the **General** tab, scroll down to find **Web API Key**.

### B. If you need the Realtime Database URL
1. In the left navigation, click **Build** &rarr; **Realtime Database**.
2. Look at the top banner:
   `https://smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app`
3. The database rules allow public read for Flutter and authenticated write for ESP8266.

### C. If you want to change the Hardware Password manually in Firebase Console
1. In the left navigation, click **Build** &rarr; **Authentication**.
2. Click the **Users** tab.
3. Locate `esp1@smartfiredetection.local`.
4. Click the three dots (`...`) on the right side &rarr; Select **Reset password** or delete and re-add.
5. If changed, simply update the new password in `firmware/esp1_detection/secrets.h` and `.env`.

### D. If you need the Python Admin Key (`serviceAccountKey.json`)
1. Go to **Project settings** &rarr; **Service accounts** tab.
2. Under "Firebase Admin SDK", select Python.
3. Click the button **Generate new private key**.
4. Save the downloaded `.json` file in `d:\StartUp\Fire_Safety\serviceAccountKey.json`.
