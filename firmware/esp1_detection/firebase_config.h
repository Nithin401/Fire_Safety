#ifndef FIREBASE_CONFIG_H
#define FIREBASE_CONFIG_H

// =====================================================================
// FIRESHIELD AI — ESP8266 & MULTI-INTEGRATION HARDWARE CREDENTIALS
// =====================================================================

// Wi-Fi Access Point Credentials
#define WIFI_SSID     "YOUR_WIFI_NAME"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Firebase Realtime Database Host (WITHOUT "https://" and NO trailing slash)
#define DATABASE_URL  "smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"

// Firebase Web API Key
#define API_KEY       "AIzaSyCxnGiInekI9FX6f7yUPuwxucYpHrUZWws"

// Firebase Authentication Credentials
// (Created in Firebase Console -> Authentication -> Users)
#define USER_EMAIL    "esp1@smartfiredetection.local"
#define USER_PASSWORD "Esp1SecurePass123"

// Multi-Integration Local Backend Server (Python Hybrid AI Server)
// Replace with your laptop/computer's local LAN IP address:
#define BACKEND_SERVER_URL  "http://192.168.1.100:5000/api/v1/telemetry"
#define DEVICE_API_KEY      "fireshield_local_dev_key_2026"

// Node Identification & Telemetry Metadata
#define DEVICE_ID           "ESP1"
#define EXPERIMENT_ID       "EXP001"
#define ROOM_ID             "Kitchen_Zone_A"

#endif // FIREBASE_CONFIG_H
