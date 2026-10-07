#ifndef FIREBASE_CONFIG_H
#define FIREBASE_CONFIG_H

// =====================================================================
// FIRESHIELD AI — ESP8266 HARDWARE & NETWORK CONFIGURATION
// =====================================================================

// If local private secrets.h exists, include it (secrets.h is git-ignored)
#if __has_include("secrets.h")
  #include "secrets.h"
#endif

// 1. Wi-Fi Access Point Credentials (2.4 GHz only)
#ifndef WIFI_SSID
  #define WIFI_SSID     "YOUR_WIFI_NAME"
#endif
#ifndef WIFI_PASSWORD
  #define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#endif

// 2. Firebase Realtime Database Configuration
// Host WITHOUT "https://" and NO trailing slash:
#define DATABASE_URL  "smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"

// Firebase Web API Key (Client-side identifier, safe for device client usage)
#define API_KEY       "AIzaSyCxnGiInekI9FX6f7yUPuwxucYpHrUZWws"

// Firebase Authentication Credentials
#define USER_EMAIL    "esp1@smartfiredetection.local"
#ifndef USER_PASSWORD
  #define USER_PASSWORD "YOUR_FIREBASE_AUTH_PASSWORD"
#endif

// Node Identification & Telemetry Metadata
#define DEVICE_ID     "ESP1"
#define ROOM_ID       "living_room"
#define EXPERIMENT_ID "EXP001"

#endif // FIREBASE_CONFIG_H
