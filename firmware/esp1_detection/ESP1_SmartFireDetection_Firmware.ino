/* =====================================================================
   FIRESHIELD AI — SMART FIRE DETECTION & TELEMETRY SYSTEM
   ESP1 DETECTION NODE FIRMWARE (ESP8266 NodeMCU / ESP-12E)
   =====================================================================
   Platform: NodeMCU 1.0 (ESP-12E Module)
   Architecture: Real-time Multi-Sensor Fusion + Firebase RTDB + ESP-NOW

   EXACT TARGET HARDWARE PIN ARCHITECTURE:
     - ESP8266 D1 / GPIO5 -> I2C SCL (Shared: BME280 SCL + ADS1115 SCL)
     - ESP8266 D2 / GPIO4 -> I2C SDA (Shared: BME280 SDA + ADS1115 SDA)
     - ESP8266 D5 / GPIO14 -> SG90 Servo Signal (0° to 180° Directional Scanning)
     - ESP8266 3V3         -> BME280 VCC + ADS1115 VDD
     - ESP8266 GND         -> Common Ground Bus

   ADS1115 (16-bit I2C ADC @ 0x48):
     - Channel A0: KY-026 Flame Sensor (Analog AO)
     - Channel A1: MQ-2 Gas/Smoke Sensor (Analog AO via 10k/15k divider)
     - Channel A2: Unused / Reserved
     - Channel A3: Unused / Reserved

   DISCONNECTED PINS (By Specification):
     - KY-026 DO -> NOT CONNECTED (Flame detection is pure analog via ADS1115 A0)
     - MQ-2 DO   -> NOT CONNECTED

   POWER & ELECTRICAL SAFETY:
     - ADS1115 VDD is 3.3V (Max safe analog input is 3.6V).
     - MQ-2 runs on 5V. A 10k/15k voltage divider steps down 5V -> 3.0V (ratio 0.60).
     - Servo power (5V) MUST be powered from an external supply or dedicated rail
       with shared common ground to prevent ESP8266 brownout resets.

   REQUIRED ARDUINO LIBRARIES:
     - ESP8266 Core (by ESP8266 Community)
     - Servo (bundled with ESP8266 core)
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
#include <time.h>
#include "firebase_config.h"

extern "C" {
  #include "user_interface.h"
}

// =====================================================================
// 1. PIN CONFIGURATION & VOLTAGE SCALING
// =====================================================================

#define I2C_SDA_PIN        4    // D2 / GPIO4 (Shared I2C SDA)
#define I2C_SCL_PIN        5    // D1 / GPIO5 (Shared I2C SCL)
#define SCAN_SERVO_PIN    14    // D5 / GPIO14 (Target Servo Signal)

#define ADS1115_I2C_ADDR      0x48
#define ADS1115_CHANNEL_FLAME 0   // Channel A0 <- KY-026 Analog AO
#define ADS1115_CHANNEL_GAS   1   // Channel A1 <- MQ-2 Analog AO
#define ADS1115_GAIN          GAIN_ONE  // +/-4.096V range, 0.125 mV/bit

// Voltage divider ratio: R1=10k, R2=15k -> ratio = 15/25 = 0.60
// Set to 1.0f if sensor analog output is strictly <= 3.3V.
#define FLAME_DIVIDER_RATIO 1.0f  // Direct wire from KY-026 AO to ADS1115 A0 (as in diagram)
#define GAS_DIVIDER_RATIO   1.0f  // Direct wire from MQ-2 AO to ADS1115 A1 (as in diagram)

// Timing Cadence (millis-based non-blocking)
#define SENSOR_SAMPLE_INTERVAL   1000UL   // 1 Hz synchronized multi-sensor sampling
#define FIREBASE_UPLOAD_INTERVAL 1000UL   // 1 Hz upload cadence
#define SERVO_SCAN_INTERVAL        40UL   // Servo step cadence (smooth sweeping)
#define SERVO_SCAN_STEP             3     // Degrees per sweep step
#define ESPNOW_SEND_INTERVAL       80UL   // ESP-NOW packet cadence
#define WIFI_RETRY_INTERVAL     10000UL   // Background Wi-Fi check (10 seconds)
#define NTP_RESYNC_INTERVAL (6UL * 3600UL * 1000UL) // Resync NTP every 6 hours

// Buffer & Calibration
#define SAMPLE_BUFFER_SIZE 20             // Stores ~20s offline backlog in RAM
#define MQ2_WARMUP_MS     (60UL * 1000UL) // 60s heater warm-up period

// Prototype Rule-Based Thresholds (Configurable)
// Note: Lower ADC on KY-026 photodiode indicates higher infrared flame radiation
#define FLAME_ANALOG_FIRE_THRESHOLD      8000   // Raw ADC below this = flame detected
#define FLAME_ANALOG_CRITICAL_THRESHOLD  4000   // Raw ADC below this = intense/close fire
#define GAS_WARNING_RAW_THRESHOLD       12000   // Elevated gas/smoke above baseline
#define GAS_PREFIRE_RAW_THRESHOLD       18000   // High combustion gas accumulation

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
  int32_t wifiRssi;
  float temperature;
  float humidity;
  float pressure;
  int16_t flameRaw;
  float flameVoltage;
  int16_t gasRaw;
  float gasVoltage;
  FireState fireState;
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

// ESP2 Receiver MAC Address (Adjust to match your responder node)
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
  if (now < 1700000000) { // Timestamp before ~2023 indicates not synced yet
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
    Serial.print(F("RSSI       : ")); Serial.print(WiFi.RSSI()); Serial.println(F(" dBm"));
    startNtp();
  } else {
    wifiWasConnected = false;
    Serial.println(F("Wi-Fi offline. Continuing autonomous fire detection..."));
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

  // Initialize BME280 (autoprobes address 0x76 then 0x77)
  bmeOK = bme.begin(0x76, &Wire);
  if (!bmeOK) {
    bmeOK = bme.begin(0x77, &Wire);
  }
  Serial.println(bmeOK ? F("BME280  : OK (I2C)") : F("BME280  : NOT FOUND (Check wiring/address 0x76/0x77)"));

  // Initialize ADS1115 16-bit ADC
  adsOK = ads.begin(ADS1115_I2C_ADDR, &Wire);
  if (adsOK) {
    ads.setGain(ADS1115_GAIN);
    Serial.println(F("ADS1115 : OK (I2C Address 0x48)"));
  } else {
    Serial.println(F("ADS1115 : NOT FOUND (Check ADDR pin connected to GND)"));
  }
}

void initFirebase() {
  fbConfig.host = DATABASE_URL;
  fbConfig.api_key = API_KEY;
  fbAuth.user.email = USER_EMAIL;
  fbAuth.user.password = USER_PASSWORD;

  fbConfig.timeout.serverResponse = 4000; // 4s timeout prevents main loop stall
  Firebase.begin(&fbConfig, &fbAuth);
  Firebase.reconnectWiFi(true);
  fbdo.setResponseSize(2048);

  firebaseReady = true;
  Serial.println(F("Firebase: Initialized with Authentication"));
}

// =====================================================================
// 7. DIRECTIONAL SERVO SCANNING
// =====================================================================

void scanForFire() {
  if (millis() - lastScanTime < SERVO_SCAN_INTERVAL) return;
  lastScanTime = millis();

  scanServo.write(scanAngle);

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
  s.wifiRssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -100;
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

  // ---- Read ADS1115 (A0: KY-026 AO, A1: MQ-2 AO) ----
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

  // ---- Directional Azimuth Tracking ----
  s.servoAngle = (uint8_t)(fireDetected ? fireAngle : scanAngle);

  // ---- Rule-Based Fire State Evaluation (Pure Analog) ----
  bool flameDetectedNow = (adsOK && s.flameRaw < FLAME_ANALOG_FIRE_THRESHOLD);
  bool flameCriticalNow = (adsOK && s.flameRaw < FLAME_ANALOG_CRITICAL_THRESHOLD);
  bool mq2WarmedUp      = (millis() - systemStartMs > MQ2_WARMUP_MS);

  if (flameCriticalNow) {
    s.fireState = STATE_CRITICAL;
    fireDetected = true;
    fireAngle = scanAngle;
  } else if (flameDetectedNow) {
    s.fireState = STATE_FIRE;
    fireDetected = true;
    fireAngle = scanAngle;
  } else if (mq2WarmedUp && s.sensorsValid && s.gasRaw > GAS_PREFIRE_RAW_THRESHOLD) {
    s.fireState = STATE_PRE_FIRE;
    fireDetected = false;
  } else if (mq2WarmedUp && s.sensorsValid && s.gasRaw > GAS_WARNING_RAW_THRESHOLD) {
    s.fireState = STATE_WARNING;
    fireDetected = false;
  } else {
    s.fireState = STATE_NORMAL;
    fireDetected = false;
  }

  lastLoggedFireState = s.fireState;

  // ---- Push into RAM Circular Ring Buffer ----
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
// 9. FIREBASE REALTIME DATABASE UPLOAD
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
  json.set("room_id", ROOM_ID);
  json.set("experiment_id", EXPERIMENT_ID);
  json.set("temperature", s.temperature);
  json.set("humidity", s.humidity);
  json.set("pressure", s.pressure);
  json.set("flame_raw", s.flameRaw);
  json.set("flame_voltage", s.flameVoltage);
  json.set("flame_volt", s.flameVoltage);
  json.set("gas_raw", s.gasRaw);
  json.set("gas_voltage", s.gasVoltage);
  json.set("gas_volt", s.gasVoltage);
  json.set("fire_state", fireStateToStr(s.fireState));
  json.set("label", fireStateToStr(s.fireState));
  json.set("servo_angle", s.servoAngle);
  json.set("sensors_valid", s.sensorsValid);
  json.set("uptime_ms", (double)s.uptimeMs);
  json.set("wifi_rssi", (int)s.wifiRssi);

  // Exact path: /devices/ESP1/readings/<unique_push_id>
  String path = String("/devices/") + DEVICE_ID + "/readings";

  bool ok = Firebase.pushJSON(fbdo, path, json);

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
  Serial.println(F("SMART FIRE DETECTION — ESP1 LIVE TELEMETRY"));
  Serial.println(F("========================================"));
  Serial.print(F("Device      : ")); Serial.println(DEVICE_ID);
  Serial.print(F("WiFi RSSI   : ")); Serial.print(s.wifiRssi); Serial.println(F(" dBm"));
  Serial.println();
  Serial.print(F("Temperature : ")); Serial.print(s.temperature, 2); Serial.println(F(" °C"));
  Serial.print(F("Humidity    : ")); Serial.print(s.humidity, 2); Serial.println(F(" %"));
  Serial.print(F("Pressure    : ")); Serial.print(s.pressure, 2); Serial.println(F(" hPa"));
  Serial.println();
  Serial.print(F("Flame Raw   : ")); Serial.print(s.flameRaw);
  Serial.print(F(" (")); Serial.print(s.flameVoltage, 3); Serial.println(F(" V) [ADS1115 A0]"));
  Serial.print(F("Gas Raw     : ")); Serial.print(s.gasRaw);
  Serial.print(F(" (")); Serial.print(s.gasVoltage, 3); Serial.println(F(" V) [ADS1115 A1]"));
  Serial.println();
  Serial.print(F("Fire State  : ")); Serial.println(fireStateToStr(s.fireState));
  Serial.print(F("Servo Angle : ")); Serial.print(s.servoAngle); Serial.println(F("° [D5/GPIO14]"));
  Serial.println();

  if (uploaded) {
    Serial.println(F("Firebase    : UPLOADED (OK)"));
  } else {
    Serial.println(F("Firebase    : QUEUED (Pending network)"));
    if (errorMsg.length() > 0) {
      Serial.print(F("Error Reason: ")); Serial.println(errorMsg);
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
  Serial.println(F(" FIRESHIELD AI — ESP1 ALL-IN-ONE NODE"));
  Serial.println(F(" Target Pin Architecture: D5 Servo, A0/A1 ADC"));
  Serial.println(F("========================================"));

  scanServo.attach(SCAN_SERVO_PIN);
  scanServo.write(90);
  delay(300);

  startWiFi();

  // ESP-NOW Configuration
  int channel = WiFi.channel();
  if (channel < 1 || channel > 13) channel = 6;
  wifi_set_channel(channel);

  Serial.println(F("Initializing ESP-NOW controller..."));
  if (esp_now_init() != 0) {
    Serial.println(F("ESP-NOW init failed. Continuing local detection."));
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

  // Priority 1: Servo Action & High-Speed ESP-NOW Dispatch
  if (!fireDetected) {
    scanForFire();
    if (millis() - lastSendTime >= ESPNOW_SEND_INTERVAL) {
      lastSendTime = millis();
      sendFireData(false, scanAngle);
    }
  } else {
    scanServo.write(fireAngle);
    if (millis() - lastSendTime >= ESPNOW_SEND_INTERVAL) {
      lastSendTime = millis();
      sendFireData(true, fireAngle);
    }

    if (!previousFire) {
      previousFire = true;
      Serial.println(F("****************************************"));
      Serial.print(F("🔥 FIRE DETECTED! TARGET AZIMUTH: ")); Serial.print(fireAngle); Serial.println(F("°"));
      Serial.println(F("****************************************"));
    }
  }

  // Priority 2: 1 Hz Synchronized Multi-Sensor Sampling
  if (millis() - lastSampleTime >= SENSOR_SAMPLE_INTERVAL) {
    lastSampleTime = millis();
    collectSensorSample();
  }

  // Priority 3: Non-Blocking Firebase RTDB Upload
  bool dueForUpload = (millis() - lastUploadAttempt >= FIREBASE_UPLOAD_INTERVAL);
  bool backlog = (bufCount > 1);

  if (bufCount > 0 && (dueForUpload || backlog)) {
    lastUploadAttempt = millis();
    uint8_t currentCount = bufCount;
    bool uploaded = uploadOldestSample();

    if (uploaded && currentCount > 0) {
      uint8_t readIdx = (bufHead == 0) ? (SAMPLE_BUFFER_SIZE - 1) : (bufHead - 1);
      printSerialStatus(sampleBuffer[readIdx], true);
    } else if (!uploaded) {
      uint8_t peekIdx = bufHead;
      printSerialStatus(sampleBuffer[peekIdx], false, fbdo.errorReason());
    }
  }
}
