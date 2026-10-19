# FireShield AI: Notification Architecture and Trade-Off Analysis

## Executive Summary

FireShield AI requires a notification delivery system that:
1. **Completely eliminates Firebase SDKs, Firebase Auth, and FCM configuration**.
2. **Preserves existing ESP8266 firmware** and the 6-field ThingSpeak data contract.
3. **Distinguishes critical hardware fire alerts from statistical room-baseline anomalies**.
4. **Delivers timely notifications** to both desktop web browsers and mobile phones.

---

## 1. Architectural Comparison of Notification Options

| Feature / Criteria | Option A: Standard Web Push with VAPID | Option B: ntfy HTTP Publishing (Mobile App) | Option C: OneSignal / Managed Push |
| :--- | :--- | :--- | :--- |
| **Primary Target** | Desktop & Mobile Web Browsers | Native Android & iOS Smartphones | Unified Web & Mobile Push |
| **Firebase Dependency** | **Zero Firebase SDKs** in app or backend | **Zero Firebase SDKs** in app or backend | Still relies on platform push (FCM / APNs) under the hood |
| **Cost** | 100% Free & Open Standards (W3C Push API) | Free hosted public service (`ntfy.sh`) or self-hosted | Free tier with subscriber caps |
| **Client Requirements** | Modern browser (Chrome, Edge, Firefox, Safari 16+) | Official ntfy app (Google Play / App Store) or Web App | OneSignal SDK integrated in client app |
| **Private Credentials on Client** | **None** (Only public VAPID key sent to browser) | **None** (Topic-based subscription) | App ID / client keys |
| **Background Execution Reliability** | Reliable when browser is running or OS supports push service worker | **Highest on Android** via foreground service; iOS subject to OS background execution limits | Good, but subject to OEM battery killer restrictions |
| **Setup Complexity** | Low-Medium (VAPID key pair + Service Worker) | **Minimal (Zero configuration)**; HTTP POST to topic | High (Requires account, certificates, dashboard setup) |

---

## 2. Chosen Architecture: Dual-Channel Delivery

To balance ease-of-use with zero-Firebase constraints, FireShield AI implements a **dual-channel notification architecture**:

### Channel 1: Mobile Push via `ntfy`
* **Mechanism**: When the Flask Risk Engine triggers a hazard event, it issues an HTTP `POST` to `https://ntfy.sh/<configured_topic>`.
* **Payload**: Includes priority (1–5), emoji tags (`fire`, `warning`, `thermometer`), descriptive title, sensor metrics, and a `Click` URL pointing to the FireShield dashboard.
* **Client**: User downloads the free, open-source ntfy application on Android or iOS and subscribes to the topic (e.g. `fireshield_alerts_3534677`).
* **Android Advantage**: ntfy supports an optional persistent foreground WebSocket connection on Android, ensuring immediate delivery even when Google Play Services or Firebase are unavailable.

### Channel 2: Browser Background Push via VAPID
* **Mechanism**: Implements the W3C Push API and IETF Web Push protocol (`pywebpush`).
* **Keys**: VAPID public/private key pair generated once and persisted in `data/vapid_keys.json`. Only the public key is exposed to the browser.
* **Service Worker**: `static/service-worker.js` listens for push events, wakes up in the background, displays native OS notifications, and handles click navigation.
* **Unsubscription & 410 Handling**: When subscriptions expire or are revoked, the backend receives HTTP 410 Gone from the browser push service (Mozilla, Google, Apple) and automatically deactivates the record in SQLite.

---

## 3. Important Platform Constraints & Trade-Offs

### A. Native Flutter Mobile App Background Push
* Android and iOS restrict background execution of third-party apps to preserve battery life.
* **Local Notifications alone cannot wake up a sleeping app** when a new ThingSpeak record arrives unless a background polling service or native push infrastructure (FCM / APNs) is configured.
* **Recommendation**: Using the separate, battery-optimized ntfy app provides reliable background delivery without bloating the Flutter project with proprietary push SDKs.

### B. Mixed Content & HTTPS Requirement
* Modern browsers require a **Secure Context (HTTPS)** for Web Push API registration (`navigator.serviceWorker.register()` and `PushManager.subscribe()`).
* For local development, `http://localhost` and `http://127.0.0.1` are treated as secure contexts by Chrome and Edge.
* For remote access over the internet or LAN IP (`http://192.168.x.x`), an HTTPS reverse proxy (e.g. Caddy, Nginx, or Cloudflare Tunnel) is required for browser Web Push. ntfy mobile notifications work over standard HTTPS without any reverse proxy setup.
