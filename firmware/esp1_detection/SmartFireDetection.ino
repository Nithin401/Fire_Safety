/* =====================================================================
   FIRESHIELD AI — SMART FIRE DETECTION & TELEMETRY SYSTEM
   ALL-IN-ONE ESP1 HARDWARE FIRMWARE (ESP8266)
   =====================================================================
   Platform: ESP8266 (NodeMCU 1.0 / WeMos D1 Mini / ESP-12E)
   Architecture: Real-time Multi-Sensor Fusion + Firebase RTDB + ESP-NOW
   
   SENSORS & ACTUATORS:
     - BME280 (I2C 0x76 or 0x77): Ambient Temperature, Humidity, Pressure
     - ADS1115 (I2C 0x48):
         * Channel A0: KY-026 Flame Sensor (Analog AO via voltage divider)
         * Channel A1: MQ-2 Gas/Smoke Sensor (Analog AO via voltage divider)
     - KY-026 DO (GPIO14 / D5): High-speed digital flame trigger
     - SG90 Servo (GPIO12 / D6): 0° to 180° directional scanning & fire lock-on
     - ESP-NOW: Fast peer-to-peer radio link to ESP2 Extinguisher Node
     - Firebase Realtime Database: 1 Hz telemetry upload to /devices/ESP1/readings
     - Multi-Integration Server: Optional dual-report to local Python AI Backend

   NOTE: TELEGRAM HAS BEEN COMPLETELY REMOVED.
   All alerts, monitoring, notifications, and dataset exports are
   handled natively by the FireShield AI Flutter App and Backend.

   REQUIRED ARDUINO LIBRARIES (Install via Arduino Library Manager):
     - ESP8266 by ESP8266 Community (Boards Manager)
     - Servo (Bundled with ESP8266 core)
     - Adafruit Unified Sensor
     - Adafruit BME280 Library
     - Adafruit ADS1X15
     - Firebase ESP8266 Client by Mobizt
   ===================================================================== */

#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Servo.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_ADS1X15.h>
#include <FirebaseESP8266.h>
#include <ESP8266HTTPClient.h>
#include <time.h>

extern "C" {
  #include "user_interface.h"
}

// =====================================================================
// 1. CONFIGURATION (Edit your Wi-Fi name & password below)
// =====================================================================

// ---- Wi-Fi Configuration ----
const char* WIFI_SSID     = "YOUR_WIFI_NAME";        // <-- Enter your Wi-Fi SSID
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";    // <-- Enter your Wi-Fi Password

// ---- Firebase Realtime Database Configuration ----
#define DATABASE_URL  "smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"
#define API_KEY       "AIzaSyCxnGiInekI9FX6f7yUPuwxucYpHrUZWws"
#define USER_EMAIL    "esp1@smartfiredetection.local"  // <-- Your Firebase Auth Email
#define USER_PASSWORD "Esp1SecurePass123"             // <-- Your Firebase Auth Password

// ---- Optional Local Multi-Integration Server ----
#define ENABLE_LOCAL_BACKEND_SERVER 0                 // Set to 1 to enable HTTP POST to local Python server
#define BACKEND_SERVER_URL          "http://192.168.1.100:5000/api/v1/telemetry"
#define BACKEND_API_KEY             "fireshield_local_dev_key_2026"

// ---- Device & Experiment Metadata ----
#define DEVICE_ID     "ESP1"
#define EXPERIMENT_ID "EXP001"                        // e.g., EXP001=Normal, EXP002=Fire, EXP003=Smoke

// ---- Pin Mapping ----
#define I2C_SDA_PIN        4    // D2 / GPIO4 (Shared I2C bus for BME280 + ADS1115)
#define I2C_SCL_PIN        5    // D1 / GPIO5
#define FLAME_SENSOR_GPIO 14    // D5 / GPIO14 (KY-026 Digital Output)
#define SCAN_SERVO_GPIO   12    // D6 / GPIO12 (Azimuth Scanning Servo)

// ---- ADS1115 Configuration ----
#define ADS1115_I2C_ADDR      0x48
#define ADS1115_CHANNEL_FLAME 0   // Channel A0 <- KY-026 Analog Output
#define ADS1115_CHANNEL_GAS   1   // Channel A1 <- MQ-2 Analog Output
#define ADS1115_GAIN          GAIN_ONE  // +/-4.096V range, 0.125 mV/bit

// Voltage divider ratio: R1=10k, R2=15k -> ratio = 15/25 = 0.6
// Set to 1.0f if sensors are powered at 3.3V without a divider.
#define FLAME_DIVIDER_RATIO 0.6f
#define GAS_DIVIDER_RATIO   0.6f

// ---- Timing Cadence (millis-based, non-blocking) ----
#define SENSOR_SAMPLE_INTERVAL   1000UL   // 1 Hz synchronized sampling
#define FIREBASE_UPLOAD_INTERVAL 1000UL   // 1 Hz upload cadence
#define SERVO_SCAN_INTERVAL        40UL   // Step interval during scanning sweep
#define SERVO_SCAN_STEP             3     // Degrees per step
#define ESPNOW_SEND_INTERVAL       80UL   // ESP-NOW packet interval
#define WIFI_RETRY_INTERVAL     10000UL   // WiFi reconnection check interval
#define NTP_RESYNC_INTERVAL (6UL * 3600UL * 1000UL) // Resync NTP every 6 hours

// ---- Ring Buffer for Offline Network Resilience ----
#define SAMPLE_BUFFER_SIZE 20             // Stores ~20s of backlog without starving ESP8266 RAM
#define MQ2_WARMUP_MS     (60UL * 1000UL) // 60s heater warm-up period

// Rule-based thresholds for prototype dataset labeling
#define GAS_WARNING_RAW_THRESHOLD  12000
#define GAS_PREFIRE_RAW_THRESHOLD  18000
#define FLAME_ANALOG_THRESHOLD      8000  // Lower ADC indicates stronger IR flame radiation

// =====================================================================
// 2. DATA STRUCTURES & ENUMS
// =====================================================================

enum FireState : uint8_t {
  STATE_NORMAL = 0,
  STATE_WARNING,
  STATE_PRE_FIRE,
  STATE_FIRE,
  STATE_CRITICAL
};

const char* fireStateToStr(FireState s) {
  switch (s) {
    case STATE_NORMAL:   return "NORMAL";
    case STATE_WARNING:  return "WARNING";
    case STATE_PRE_FIRE: return "PRE_FIRE";
    case STATE_FIRE:     return "FIRE";
    case STATE_CRITICAL: return "CRITICAL";
  }
  return "NORMAL";
}

struct SensorSample {
  uint32_t epochTime;
  unsigned long uptimeMs;
  float temperature;
  float humidity;
  float pressure;
  int16_t flameRaw;
  float flameVoltage;
  int16_t gasRaw;
  float gasVoltage;
  FireState fireState;
  uint8_t flameDigital;
  uint8_t servoAngle;
  bool sensorsValid;
};

// ESP-NOW Payload for ESP2 Extinguisher Actuator
struct FireData {
  uint8_t header;
  uint8_t fire;
  uint8_t angle;
  uint32_t packetID;
};

// =====================================================================
// 3. GLOBAL OBJECTS & STATE
// =====================================================================

// ESP2 Receiver MAC Address (Adjust to match your ESP2 board MAC)
uint8_t ESP2_MAC[] = { 0x48, 0x3F, 0xDA, 0x5F, 0x0C, 0x55 };
uint32_t packetID = 0;

Servo scanServo;
int scanAngle = 90;
int scanDirection = 1;
unsigned long lastScanTime = 0;

bool fireDetected = false;
bool previousFire = false;
int fireAngle = 90;

unsigned long lastSendTime = 0;
unsigned long lastWiFiAttempt = 0;
bool wifiWasConnected = false;

Adafruit_BME280 bme;
bool bmeOK = false;

Adafruit_ADS1115 ads;
bool adsOK = false;

FirebaseData fbdo;
FirebaseAuth fbAuth;
FirebaseConfig fbConfig;
bool firebaseReady = false;

unsigned long systemStartMs = 0;
unsigned long lastNtpSync = 0;
bool ntpSynced = false;

unsigned long lastSampleTime = 0;
unsigned long lastUploadAttempt = 0;

SensorSample sampleBuffer[SAMPLE_BUFFER_SIZE];
uint8_t bufHead = 0;
uint8_t bufCount = 0;
uint16_t droppedSamples = 0;

FireState lastLoggedFireState = STATE_NORMAL;

// =====================================================================
// 4. NTP TIME SYNCHRONIZATION
// =====================================================================

void startNtp() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  lastNtpSync = millis();
}

bool getEpochIfSynced(uint32_t &epochOut) {
  time_t now = time(nullptr);
  if (now < 1700000000) { // Timestamp before ~2023 means NTP not synced yet
    return false;
  }
  epochOut = (uint32_t)now;
  ntpSynced = true;
  return true;
}

bool formatIsoTimestamp(uint32_t epoch, char* out, size_t outLen) {
  if (epoch == 0) {
    snprintf(out, outLen, "");
    return false;
  }
  time_t t = (time_t)epoch;
  struct tm* tmStruct = gmtime(&t);
  strftime(out, outLen, "%Y-%m-%dT%H:%M:%SZ", tmStruct);
  return true;
}

// =====================================================================
// 5. WI-FI & ESP-NOW SETUP
// =====================================================================

void startWiFi() {
  Serial.println();
  Serial.println(F("Starting Wi-Fi..."));

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  Serial.print(F("Connecting to Wi-Fi"));
  while (WiFi.status() != WL_CONNECTED && millis() - start < 5000) {
    delay(100);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiWasConnected = true;
    Serial.println(F("========================================"));
    Serial.println(F("WI-FI CONNECTED"));
    Serial.println(F("========================================"));
    Serial.print(F("IP Address : ")); Serial.println(WiFi.localIP());
    Serial.print(F("Channel    : ")); Serial.println(WiFi.channel());
    Serial.print(F("ESP1 MAC   : ")); Serial.println(WiFi.macAddress());
    startNtp();
  } else {
    wifiWasConnected = false;
    Serial.println(F("Wi-Fi connection pending. Continuing autonomous fire detection..."));
  }
}

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.println(F("\nWi-Fi reconnected successfully!"));
      Serial.print(F("IP: ")); Serial.println(WiFi.localIP());
      startNtp();
    }
    if (millis() - lastNtpSync >= NTP_RESYNC_INTERVAL) {
      startNtp();
    }
    return;
  }

  wifiWasConnected = false;
  if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
    lastWiFiAttempt = millis();
    Serial.println(F("\nRetrying Wi-Fi connection in background..."));
    WiFi.disconnect();
    delay(50);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

void sendFireData(bool fire, int angle) {
  FireData packet;
  packet.header = 0xAA;
  packet.fire = fire ? 1 : 0;
  packet.angle = constrain(angle, 0, 180);
  packet.packetID = ++packetID;

  esp_now_send(ESP2_MAC, (uint8_t*)&packet, sizeof(packet));
}

// =====================================================================
// 6. SENSORS & FIREBASE INITIALIZATION
// =====================================================================

void initSensors() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

  // Initialize BME280 (tries 0x76 then 0x77)
  bmeOK = bme.begin(0x76, &Wire);
  if (!bmeOK) {
    bmeOK = bme.begin(0x77, &Wire);
  }
  Serial.println(bmeOK ? F("BME280  : OK (I2C)") : F("BME280  : NOT FOUND (Check wiring 0x76/0x77)"));

  // Initialize ADS1115 16-bit ADC
  adsOK = ads.begin(ADS1115_I2C_ADDR, &Wire);
  if (adsOK) {
    ads.setGain(ADS1115_GAIN);
    Serial.println(F("ADS1115 : OK (I2C Address 0x48)"));
  } else {
    Serial.println(F("ADS1115 : NOT FOUND (Check ADDR pin to GND)"));
  }
}

void initFirebase() {
  fbConfig.host = DATABASE_URL;
  fbConfig.api_key = API_KEY;
  fbAuth.user.email = USER_EMAIL;
  fbAuth.user.password = USER_PASSWORD;

  fbConfig.timeout.serverResponse = 4000; // 4s timeout prevents loop stall
  Firebase.begin(&fbConfig, &fbAuth);
  Firebase.reconnectWiFi(true);
  fbdo.setResponseSize(2048);

  firebaseReady = true;
  Serial.println(F("Firebase: Initialized with Authentication"));
}

// =====================================================================
// 7. LOCAL FIRE DETECTION & SERVO SCANNING
// =====================================================================

bool flameDigitalDetected() {
  int lowCount = 0;
  for (int i = 0; i < 3; i++) {
    if (digitalRead(FLAME_SENSOR_GPIO) == LOW) lowCount++;
    delayMicroseconds(250);
  }
  return (lowCount >= 2);
}

void scanForFire() {
  if (millis() - lastScanTime < SERVO_SCAN_INTERVAL) return;
  lastScanTime = millis();

  scanServo.write(scanAngle);

  bool flame = flameDigitalDetected();
  if (flame) {
    fireDetected = true;
    fireAngle = scanAngle;
    return;
  }

  scanAngle += scanDirection * SERVO_SCAN_STEP;
  if (scanAngle >= 180) {
    scanAngle = 180;
    scanDirection = -1;
  } else if (scanAngle <= 0) {
    scanAngle = 0;
    scanDirection = 1;
  }
}

// =====================================================================
// 8. MULTI-SENSOR SAMPLING (1 Hz non-blocking)
// =====================================================================

void collectSensorSample() {
  SensorSample s;
  memset(&s, 0, sizeof(s));

  s.uptimeMs = millis();
  uint32_t epoch = 0;
  getEpochIfSynced(epoch);
  s.epochTime = epoch;
  s.sensorsValid = true;

  // ---- Read BME280 ----
  if (bmeOK) {
    float t = bme.readTemperature();
    float h = bme.readHumidity();
    float p = bme.readPressure() / 100.0F;

    if (isnan(t) || isnan(h) || isnan(p) || t < -40 || t > 85 || h < 0 || h > 100) {
      s.sensorsValid = false;
    } else {
      s.temperature = t;
      s.humidity = h;
      s.pressure = p;
    }
  } else {
    s.sensorsValid = false;
  }

  // ---- Read ADS1115 (KY-026 AO & MQ-2 AO) ----
  if (adsOK) {
    int16_t rawFlame = ads.readADC_SingleEnded(ADS1115_CHANNEL_FLAME);
    int16_t rawGas   = ads.readADC_SingleEnded(ADS1115_CHANNEL_GAS);

    if (rawFlame < 0 || rawGas < 0 || rawFlame > 32767 || rawGas > 32767) {
      s.sensorsValid = false;
    } else {
      s.flameRaw = rawFlame;
      s.gasRaw = rawGas;
      s.flameVoltage = ads.computeVolts(rawFlame) / FLAME_DIVIDER_RATIO;
      s.gasVoltage   = ads.computeVolts(rawGas) / GAS_DIVIDER_RATIO;
    }
  } else {
    s.sensorsValid = false;
  }

  // ---- Digital State & Directional Azimuth ----
  s.flameDigital = fireDetected ? 1 : 0;
  s.servoAngle   = (uint8_t)(fireDetected ? fireAngle : scanAngle);

  // ---- Transparent Rule-Based Fire State Evaluation ----
  bool mq2WarmedUp = (millis() - systemStartMs > MQ2_WARMUP_MS);

  if (s.flameDigital == 1 && s.flameRaw < FLAME_ANALOG_THRESHOLD) {
    s.fireState = STATE_CRITICAL;
  } else if (s.flameDigital == 1) {
    s.fireState = STATE_FIRE;
  } else if (mq2WarmedUp && s.sensorsValid && s.gasRaw > GAS_PREFIRE_RAW_THRESHOLD) {
    s.fireState = STATE_PRE_FIRE;
  } else if (mq2WarmedUp && s.sensorsValid && s.gasRaw > GAS_WARNING_RAW_THRESHOLD) {
    s.fireState = STATE_WARNING;
  } else {
    s.fireState = STATE_NORMAL;
  }

  lastLoggedFireState = s.fireState;

  // ---- Push into RAM Ring Buffer ----
  if (bufCount >= SAMPLE_BUFFER_SIZE) {
    droppedSamples++;
    bufHead = (bufHead + 1) % SAMPLE_BUFFER_SIZE;
    bufCount--;
  }

  uint8_t writeIdx = (bufHead + bufCount) % SAMPLE_BUFFER_SIZE;
  sampleBuffer[writeIdx] = s;
  bufCount++;
}

// =====================================================================
// 9. FIREBASE & LOCAL SERVER UPLOAD
// =====================================================================

bool uploadOldestSample() {
  if (bufCount == 0) return true;
  if (WiFi.status() != WL_CONNECTED || !Firebase.ready()) return false;

  SensorSample &s = sampleBuffer[bufHead];

  char isoTime[25];
  bool haveIso = formatIsoTimestamp(s.epochTime, isoTime, sizeof(isoTime));

  FirebaseJson json;
  if (haveIso) {
    json.set("timestamp", isoTime);
  } else {
    json.set("timestamp", String(s.uptimeMs));
  }
  json.set("device_id", DEVICE_ID);
  json.set("experiment_id", EXPERIMENT_ID);
  json.set("temperature", s.temperature);
  json.set("humidity", s.humidity);
  json.set("pressure", s.pressure);
  json.set("flame_raw", s.flameRaw);
  json.set("flame_voltage", s.flameVoltage);
  json.set("gas_raw", s.gasRaw);
  json.set("gas_voltage", s.gasVoltage);
  json.set("flame_digital", s.flameDigital);
  json.set("fire_state", fireStateToStr(s.fireState));
  json.set("servo_angle", s.servoAngle);
  json.set("sensors_valid", s.sensorsValid);
  json.set("uptime_ms", (double)s.uptimeMs);

  // Exact path: /devices/ESP1/readings/<unique_push_id>
  String path = String("/devices/") + DEVICE_ID + "/readings";
  bool ok = Firebase.pushJSON(fbdo, path, json);

  // Optional: Post to local Multi-Integration server
#if ENABLE_LOCAL_BACKEND_SERVER
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    http.begin(client, BACKEND_SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", BACKEND_API_KEY);

    String localJson = "{"
      "\"device_id\":\"" + String(DEVICE_ID) + "\","
      "\"flame_raw\":" + String(s.flameRaw) + ","
      "\"temp_c\":" + String(s.temperature, 2) + ","
      "\"humidity\":" + String(s.humidity, 2) + ","
      "\"gas_raw\":" + String(s.gasRaw) + ","
      "\"fire_angle\":" + String(s.servoAngle) + ","
      "\"is_fire\":" + String(s.flameDigital == 1 ? "true" : "false") +
    "}";
    http.POST(localJson);
    http.end();
  }
#endif

  if (ok) {
    bufHead = (bufHead + 1) % SAMPLE_BUFFER_SIZE;
    bufCount--;
  }
  return ok;
}

// =====================================================================
// 10. SERIAL MONITOR TELEMETRY FORMAT
// =====================================================================

void printSerialStatus(const SensorSample &s, bool uploaded, const String &errorMsg = "") {
  Serial.println(F("========================================"));
  Serial.println(F("SMART FIRE DETECTION"));
  Serial.println(F("========================================"));
  Serial.print(F("Device      : ")); Serial.println(DEVICE_ID);
  Serial.println();
  Serial.print(F("Temperature : ")); Serial.print(s.temperature, 2); Serial.println(F(" °C"));
  Serial.print(F("Humidity    : ")); Serial.print(s.humidity, 2); Serial.println(F(" %"));
  Serial.print(F("Pressure    : ")); Serial.print(s.pressure, 2); Serial.println(F(" hPa"));
  Serial.println();
  Serial.print(F("Flame Raw   : ")); Serial.println(s.flameRaw);
  Serial.print(F("Flame Volt  : ")); Serial.print(s.flameVoltage, 3); Serial.println(F(" V"));
  Serial.println();
  Serial.print(F("Gas Raw     : ")); Serial.println(s.gasRaw);
  Serial.print(F("Gas Volt    : ")); Serial.print(s.gasVoltage, 3); Serial.println(F(" V"));
  Serial.println();
  Serial.print(F("Flame Digital : ")); Serial.println(s.flameDigital);
  Serial.println();
  Serial.print(F("Fire State  : ")); Serial.println(fireStateToStr(s.fireState));
  Serial.println();
  Serial.print(F("Servo Angle : ")); Serial.println(s.servoAngle);
  Serial.println();

  if (uploaded) {
    Serial.println(F("Firebase    : UPLOADED"));
  } else {
    Serial.println(F("Firebase    : QUEUED"));
    if (errorMsg.length() > 0) {
      Serial.print(F("Error       : ")); Serial.println(errorMsg);
    }
  }
  Serial.print(F("Queue Buffer: ")); Serial.print(bufCount); Serial.print(F("/")); Serial.println(SAMPLE_BUFFER_SIZE);
  if (droppedSamples > 0) {
    Serial.print(F("Dropped     : ")); Serial.println(droppedSamples);
  }
  Serial.println(F("========================================\n"));
}

// =====================================================================
// 11. SETUP
// =====================================================================

void setup() {
  Serial.begin(115200);
  delay(300);
  systemStartMs = millis();

  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F(" SMART FIRE DETECTION - ALL-IN-ONE"));
  Serial.println(F(" (Telegram completely removed)"));
  Serial.println(F("========================================"));

  pinMode(FLAME_SENSOR_GPIO, INPUT);

  scanServo.attach(SCAN_SERVO_GPIO);
  scanServo.write(90);
  delay(300);

  startWiFi();

  // ESP-NOW Configuration
  int channel = WiFi.channel();
  if (channel < 1 || channel > 13) channel = 6;
  wifi_set_channel(channel);

  Serial.println(F("Initializing ESP-NOW controller..."));
  if (esp_now_init() != 0) {
    Serial.println(F("ESP-NOW initialization failed. Continuing local detection."));
  } else {
    esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
    if (esp_now_add_peer(ESP2_MAC, ESP_NOW_ROLE_SLAVE, channel, NULL, 0) == 0) {
      Serial.println(F("ESP-NOW: ESP2 Extinguisher Peer Added."));
    }
  }

  initSensors();
  initFirebase();

  Serial.println(F("========================================"));
  Serial.println(F(" SYSTEM READY & STREAMING"));
  Serial.println(F("========================================\n"));

  lastSampleTime = millis();
  lastUploadAttempt = millis();
}

// =====================================================================
// 12. MAIN LOOP (Non-blocking priorities)
// =====================================================================

void loop() {
  checkWiFi();

  // Priority 1: High-Speed Fire Scanning & Actuation
  if (!fireDetected) {
    scanForFire();
  }

  if (fireDetected) {
    scanServo.write(fireAngle);

    // Continuous ESP-NOW signal transmission to ESP2 extinguisher
    if (millis() - lastSendTime >= ESPNOW_SEND_INTERVAL) {
      lastSendTime = millis();
      sendFireData(true, fireAngle);
    }

    if (!previousFire) {
      previousFire = true;
      Serial.println(F("****************************************"));
      Serial.print(F("🔥 FIRE DETECTED! BEARING: ")); Serial.print(fireAngle); Serial.println(F("°"));
      Serial.println(F("****************************************"));
    }

    // Check if fire has been cleared
    if (!flameDigitalDetected()) {
      delay(50);
      if (!flameDigitalDetected()) {
        fireDetected = false;
        previousFire = false;
        Serial.println(F("\nIssue Cleared: Fire Extinguished."));
        for (int i = 0; i < 4; i++) {
          sendFireData(false, fireAngle);
          delay(20);
        }
        scanAngle = fireAngle;
        scanDirection = 1;
      }
    }
  } else {
    if (millis() - lastSendTime >= ESPNOW_SEND_INTERVAL) {
      lastSendTime = millis();
      sendFireData(false, scanAngle);
    }
  }

  // Priority 2: 1 Hz Synchronized Multi-Sensor Sampling
  if (millis() - lastSampleTime >= SENSOR_SAMPLE_INTERVAL) {
    lastSampleTime = millis();
    collectSensorSample();
  }

  // Priority 3: Non-Blocking Firebase Upload
  bool dueForUpload = (millis() - lastUploadAttempt >= FIREBASE_UPLOAD_INTERVAL);
  bool backlog = (bufCount > 1);

  if (bufCount > 0 && (dueForUpload || backlog)) {
    lastUploadAttempt = millis();
    uint8_t currentCount = bufCount;
    bool uploaded = uploadOldestSample();
    
    // Print telemetry to Serial Monitor
    if (uploaded && currentCount > 0) {
      uint8_t readIdx = (bufHead == 0) ? (SAMPLE_BUFFER_SIZE - 1) : (bufHead - 1);
      printSerialStatus(sampleBuffer[readIdx], true);
    } else if (!uploaded) {
      uint8_t peekIdx = bufHead;
      printSerialStatus(sampleBuffer[peekIdx], false, fbdo.errorReason());
    }
  }
}
