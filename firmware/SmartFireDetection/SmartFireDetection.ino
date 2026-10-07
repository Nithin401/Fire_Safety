/* =====================================================================
   FIRESHIELD AI — SMART FIRE DETECTION & TELEMETRY SYSTEM
   ESP1 DETECTION NODE FIRMWARE (ESP8266 NodeMCU / ESP-12E)
   =====================================================================
   Platform: NodeMCU 1.0 (ESP-12E Module)
   Architecture: Real-time Multi-Sensor Fusion + Firebase RTDB + ESP-NOW
   
   TARGET HARDWARE WIRING:
     - ESP8266 D1 (GPIO5)  --> I2C SCL (Shared: BME280 SCL + ADS1115 SCL)
     - ESP8266 D2 (GPIO4)  --> I2C SDA (Shared: BME280 SDA + ADS1115 SDA)
     - ESP8266 D5 (GPIO14) --> SG90 Servo Signal (PWM Azimuth Angle)
     - ESP8266 3V3         --> BME280 VCC + ADS1115 VDD
     - ESP8266 GND         --> Common Ground Rail
     - External 5V / VIN   --> MQ-2 VCC + KY-026 VCC + Servo VCC

   ADS1115 (16-bit ADC @ 0x48):
     - Channel A0: KY-026 Flame Sensor (Analog AO - Grey Wire)
     - Channel A1: MQ-2 Gas/Smoke Sensor (Analog AO - Purple Wire)
     - Channel A2: Unused
     - Channel A3: Unused

   REQUIRED ARDUINO LIBRARIES (Install via Library Manager):
     1. "Firebase ESP8266 Client" by Mobizt
     2. "Adafruit BME280 Library" by Adafruit
     3. "Adafruit ADS1X15" by Adafruit
     4. "Adafruit Unified Sensor" by Adafruit
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

extern "C" {
  #include "user_interface.h"
}

// =====================================================================
// 1. CONFIGURATION (ENTER YOUR WI-FI CREDENTIALS HERE)
// =====================================================================

// Wi-Fi Access Point (2.4 GHz only, e.g. Phone Hotspot or Home Router)
const char* WIFI_SSID     = "YOUR_WIFI_NAME";        // <-- Change to your Wi-Fi Name
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";    // <-- Change to your Wi-Fi Password

// Firebase Realtime Database Host (without https:// and trailing slash)
#define DATABASE_URL  "smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"

// Firebase Web API Key
#define API_KEY       "AIzaSyCxnGiInekI9FX6f7yUPuwxucYpHrUZWws"

// Firebase Device Authentication (Rotated Secure Password)
#define USER_EMAIL    "esp1@smartfiredetection.local"
#define USER_PASSWORD "FS_esp1_Sec#2026_LiveKey!"

// Node Identification & Telemetry Metadata
#define DEVICE_ID     "ESP1"
#define ROOM_ID       "living_room"
#define EXPERIMENT_ID "EXP001"

// Pin Mapping
#define I2C_SDA_PIN        4    // D2 / GPIO4 (Shared I2C SDA)
#define I2C_SCL_PIN        5    // D1 / GPIO5 (Shared I2C SCL)
#define SCAN_SERVO_PIN    14    // D5 / GPIO14 (Servo PWM Signal)

// ADS1115 Configuration
#define ADS1115_I2C_ADDR      0x48
#define ADS1115_CHANNEL_FLAME 0   // Channel A0 <- KY-026 Analog AO
#define ADS1115_CHANNEL_GAS   1   // Channel A1 <- MQ-2 Analog AO
#define ADS1115_GAIN          GAIN_ONE  // +/-4.096V range, 0.125 mV/bit

// Direct jumper wire ratios (1.0f as wired in the schematic)
#define FLAME_DIVIDER_RATIO 1.0f
#define GAS_DIVIDER_RATIO   1.0f

// Non-blocking Timing Cadence (milliseconds)
#define SENSOR_SAMPLE_INTERVAL   1000UL   // 1 Hz synchronized sampling
#define FIREBASE_UPLOAD_INTERVAL 1000UL   // 1 Hz upload cadence
#define SERVO_SCAN_INTERVAL        40UL   // Servo sweep step interval
#define SERVO_SCAN_STEP             3     // Degrees per sweep step
#define ESPNOW_SEND_INTERVAL       80UL   // ESP-NOW packet cadence
#define WIFI_RETRY_INTERVAL     10000UL   // Background Wi-Fi check (10s)
#define NTP_RESYNC_INTERVAL (6UL * 3600UL * 1000UL) // NTP resync (6h)

// Buffer & Calibration
#define SAMPLE_BUFFER_SIZE 20             // Stores ~20s offline backlog in RAM
#define MQ2_WARMUP_MS     (60UL * 1000UL) // 60s heater warm-up period

// Rule-Based Fire Detection Thresholds
// Lower ADC on KY-026 photodiode indicates higher infrared flame radiation
#define FLAME_ANALOG_FIRE_THRESHOLD      8000   // Raw ADC < 8000 = Flame detected
#define FLAME_ANALOG_CRITICAL_THRESHOLD  4000   // Raw ADC < 4000 = Intense close flame
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

struct FireData {
  uint8_t header;
  uint8_t fire;
  uint8_t angle;
  uint32_t packetID;
};

// =====================================================================
// 3. GLOBAL OBJECTS & STATE
// =====================================================================

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
  if (now < 1700000000) {
    return false;
  }
  epochOut = (uint32_t)now;
  return true;
}

bool formatIsoTimestamp(uint32_t epoch, char* buffer, size_t bufLen) {
  if (epoch < 1700000000) return false;
  time_t t = (time_t)epoch;
  struct tm* tmInfo = gmtime(&t);
  if (!tmInfo) return false;
  snprintf(buffer, bufLen, "%04d-%02d-%02dT%02d:%02d:%02dZ",
           tmInfo->tm_year + 1900, tmInfo->tm_mon + 1, tmInfo->tm_mday,
           tmInfo->tm_hour, tmInfo->tm_min, tmInfo->tm_sec);
  return true;
}

// =====================================================================
// 5. WI-FI & ESP-NOW SETUP
// =====================================================================

void startWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  Serial.println(F("\n========================================"));
  Serial.print(F("Connecting to Wi-Fi SSID: "));
  Serial.println(WIFI_SSID);
  Serial.println(F("========================================"));

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(250);
    Serial.print(F("."));
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiWasConnected = true;
    Serial.println(F("WI-FI CONNECTED SUCCESSFULLY!"));
    Serial.print(F("IP Address : ")); Serial.println(WiFi.localIP());
    Serial.print(F("ESP1 MAC   : ")); Serial.println(WiFi.macAddress());
    Serial.print(F("RSSI       : ")); Serial.print(WiFi.RSSI()); Serial.println(F(" dBm"));
    startNtp();
  } else {
    wifiWasConnected = false;
    Serial.println(F("Wi-Fi offline. Continuing autonomous detection..."));
  }
}

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.println(F("\nWi-Fi reconnected successfully!"));
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

  bmeOK = bme.begin(0x76, &Wire);
  if (!bmeOK) {
    bmeOK = bme.begin(0x77, &Wire);
  }
  Serial.println(bmeOK ? F("BME280  : OK (I2C)") : F("BME280  : NOT FOUND (Check 0x76/0x77 wiring)"));

  adsOK = ads.begin(ADS1115_I2C_ADDR, &Wire);
  if (adsOK) {
    ads.setGain(ADS1115_GAIN);
    Serial.println(F("ADS1115 : OK (I2C Address 0x48)"));
  } else {
    Serial.println(F("ADS1115 : NOT FOUND (Check ADDR pin connected to GND)"));
  }
}

void initFirebase() {
  Serial.println(F("Configuring Firebase Realtime Database..."));
  fbConfig.host = DATABASE_URL;
  fbConfig.api_key = API_KEY;
  fbAuth.user.email = USER_EMAIL;
  fbAuth.user.password = USER_PASSWORD;

  Firebase.reconnectWiFi(true);
  fbdo.setResponseSize(1024);

  Firebase.begin(&fbConfig, &fbAuth);
  firebaseReady = true;
  Serial.println(F("Firebase client initialized."));
}

// =====================================================================
// 7. SERVO SCANNING
// =====================================================================

void scanForFire() {
  if (millis() - lastScanTime < SERVO_SCAN_INTERVAL) return;
  lastScanTime = millis();

  scanAngle += (scanDirection * SERVO_SCAN_STEP);
  if (scanAngle >= 180) {
    scanAngle = 180;
    scanDirection = -1;
  } else if (scanAngle <= 0) {
    scanAngle = 0;
    scanDirection = 1;
  }
  scanServo.write(scanAngle);
}

// =====================================================================
// 8. MULTI-SENSOR SAMPLING & CLASSIFICATION
// =====================================================================

void collectSensorSample() {
  SensorSample s;
  s.uptimeMs = millis();
  s.wifiRssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -100;

  uint32_t ep = 0;
  if (getEpochIfSynced(ep)) {
    s.epochTime = ep;
  } else {
    s.epochTime = 0;
  }

  s.sensorsValid = true;

  if (bmeOK) {
    s.temperature = bme.readTemperature();
    s.humidity    = bme.readHumidity();
    s.pressure    = bme.readPressure() / 100.0F;

    if (isnan(s.temperature) || isnan(s.humidity) || isnan(s.pressure) ||
        s.temperature < -40.0f || s.temperature > 85.0f) {
      s.sensorsValid = false;
    }
  } else {
    s.temperature = 26.0f;
    s.humidity    = 50.0f;
    s.pressure    = 1013.25f;
    s.sensorsValid = false;
  }

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

  s.servoAngle = (uint8_t)(fireDetected ? fireAngle : scanAngle);

  // Rule-Based Multi-Sensor Classification
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

  // Circular RAM Ring Buffer
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
  Serial.print(F("Room        : ")); Serial.println(ROOM_ID);
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
// 12. MAIN LOOP
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
