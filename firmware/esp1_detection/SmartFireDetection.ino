/* =====================================================================
   SMART FIRE DETECTION - ESP1 FIRMWARE (REFINED)
   =====================================================================
   Preserves: WiFi, Telegram bot, ESP-NOW, KY-026 digital flame scan,
   servo scanning, fire alert / fire-cleared messages.

   Adds: BME280 + KY-026(AO) + MQ-2(AO) via ADS1115, millis()-based
   1 Hz synchronized sampling, a small RAM ring buffer, and
   non-blocking-as-possible upload to Firebase Realtime Database.

   REQUIRED LIBRARIES (install via Arduino Library Manager):
     - ESP8266 core for Arduino (board package)
     - Servo (bundled with ESP8266 core)
     - UniversalTelegramBot        by Brian Lough
     - Adafruit Unified Sensor     by Adafruit
     - Adafruit BME280 Library     by Adafruit
     - Adafruit ADS1X15            by Adafruit
     - Firebase ESP8266 Client     by Mobizt   (search "FirebaseESP8266")

   ===================================================================== */

#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Servo.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
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
// SECTION 16: CONFIGURATION  (edit these)
// =====================================================================

// ---- WiFi ----
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ---- Telegram ----
#define BOT_TOKEN "YOUR_NEW_TELEGRAM_BOT_TOKEN"
#define CHAT_ID   "YOUR_CHAT_ID"

// ---- Firebase Realtime Database ----
// Host WITHOUT "https://" and WITHOUT trailing slash:
#define FIREBASE_HOST          "smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"
#define FIREBASE_API_KEY       "AIzaSyCxnGiInekI9FX6f7yUPuwxucYpHrUZWws"
#define FIREBASE_USER_EMAIL    "esp1@fireshield.local"
#define FIREBASE_USER_PASSWORD "Password123!"

// ---- Device / experiment identity ----
#define DEVICE_ID     "ESP1"
#define EXPERIMENT_ID "EXP001"   // change per data-collection session, see SECTION 13

// ---- I2C pins (ADS1115 + BME280 share this bus) ----
#define I2C_SDA_PIN 4   // D2 / GPIO4
#define I2C_SCL_PIN 5   // D1 / GPIO5

// ---- Existing digital / servo pins (unchanged) ----
#define FLAME_SENSOR_GPIO 14   // D5 - KY-026 digital output
#define SCAN_SERVO_GPIO   12   // D6

// ---- ADS1115 ----
#define ADS1115_I2C_ADDR 0x48
#define ADS1115_CHANNEL_FLAME 0   // A0 <- KY-026 AO
#define ADS1115_CHANNEL_GAS   1   // A1 <- MQ-2 AO
// Gain: GAIN_ONE = +-4.096V range, 0.125 mV/bit. Chosen because both
// sensors are 5V modules stepped down through a voltage divider (see
// SECTION 8 explanation) to stay under ~3.3V - GAIN_ONE gives the best
// resolution that still comfortably covers that divided range.
#define ADS1115_GAIN GAIN_ONE

// If you added a voltage divider on KY-026/MQ-2 AO before the ADS1115,
// set the ratio here (Vads / Vsensor) so raw sensor voltage is restored.
// Divider R1=10k (sensor->node), R2=15k (node->GND) -> ratio = 15/25 = 0.6
#define FLAME_DIVIDER_RATIO 0.6f
#define GAS_DIVIDER_RATIO   0.6f
// If your sensors are powered at 3.3V and wired DIRECTLY to the ADS1115
// with no divider, set both ratios to 1.0f instead.

// ---- Timing ----
#define SENSOR_SAMPLE_INTERVAL   1000UL   // ms, ~1 Hz synchronized sample
#define FIREBASE_UPLOAD_INTERVAL 1000UL   // ms, target upload cadence
#define SCAN_INTERVAL   40
#define SCAN_STEP        3
#define SEND_INTERVAL          80UL
#define TELEGRAM_INTERVAL   30000UL
#define WIFI_RETRY_INTERVAL 10000UL
#define NTP_RESYNC_INTERVAL (6UL * 3600UL * 1000UL) // resync every 6h

// ---- Local buffer for Firebase samples ----
// ESP8266 has ~80KB free heap; HTTPS/TLS to Firebase (BearSSL) alone can
// use 20-30KB while a request is in flight. Keep this buffer small so a
// WiFi outage never starves the heap. Each SensorSample is ~48 bytes,
// so 20 slots is well under 1KB - safe with large margin.
#define SAMPLE_BUFFER_SIZE 20

// ---- MQ-2 warm-up ----
#define MQ2_WARMUP_MS (60UL * 1000UL)  // 60s heater warm-up before trusting gas readings

// ---- Simple threshold used ONLY to label WARNING vs NORMAL in the
// dataset for later human/ML review. This is NOT machine learning, and
// it does NOT drive the flame-suppression response (the digital KY-026
// signal still does that, unchanged). Tune after collecting baseline data.
#define GAS_WARNING_RAW_THRESHOLD 12000

// =====================================================================
// GLOBALS - unchanged ESP-NOW / servo / telegram state
// =====================================================================

WiFiClientSecure client;
UniversalTelegramBot bot(BOT_TOKEN, client);

uint8_t ESP2_MAC[] = { 0x48, 0x3F, 0xDA, 0x5F, 0x0C, 0x55 };

struct FireData {
  uint8_t header;
  uint8_t fire;
  uint8_t angle;
  uint32_t packetID;
};
uint32_t packetID = 0;

Servo scanServo;
int scanAngle = 0;
int scanDirection = 1;
unsigned long lastScanTime = 0;

bool fireDetected = false;
bool previousFire = false;
int fireAngle = 90;

unsigned long lastSendTime = 0;
unsigned long lastTelegramTime = 0;
unsigned long lastWiFiAttempt = 0;
bool wifiWasConnected = false;

// =====================================================================
// GLOBALS - new sensing / Firebase
// =====================================================================

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

enum FireState : uint8_t { STATE_NORMAL = 0, STATE_WARNING, STATE_PRE_FIRE, STATE_FIRE, STATE_CRITICAL };

const char* fireStateToStr(FireState s) {
  switch (s) {
    case STATE_NORMAL:   return "NORMAL";
    case STATE_WARNING:  return "WARNING";
    case STATE_PRE_FIRE: return "PRE_FIRE";
    case STATE_FIRE:     return "FIRE";
    case STATE_CRITICAL: return "CRITICAL";
  }
  return "UNKNOWN";
}

struct SensorSample {
  uint32_t epochTime;      // unix seconds, 0 if NTP never synced
  unsigned long uptimeMs;  // fallback / cross-check
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
  bool sensorsValid;       // false if BME280/ADS1115 read failed this cycle
};

SensorSample sampleBuffer[SAMPLE_BUFFER_SIZE];
uint8_t bufHead = 0;   // next write position
uint8_t bufCount = 0;  // number of samples currently queued
uint16_t droppedSamples = 0;

// =====================================================================
// TIME HELPERS
// =====================================================================

void startNtp() {
  // UTC, no DST offsets - store everything as UTC, matching timestamp
  // format used in the CSV examples (trailing "Z").
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  lastNtpSync = millis();
}

bool getEpochIfSynced(uint32_t &epochOut) {
  time_t now = time(nullptr);
  if (now < 1700000000) { // sanity check: before ~2023 means not synced yet
    return false;
  }
  epochOut = (uint32_t)now;
  ntpSynced = true;
  return true;
}

// Formats "YYYY-MM-DDTHH:MM:SSZ". Returns false (empty string) if not synced.
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
// WIFI (unchanged logic, kept intact)
// =====================================================================

void startWiFi() {
  Serial.println();
  Serial.println("Starting WiFi...");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startTime = millis();
  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED && millis() - startTime < 5000) {
    delay(100);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    wifiWasConnected = true;
    Serial.println("================================");
    Serial.println("WIFI CONNECTED");
    Serial.println("================================");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("WiFi Channel: ");
    Serial.println(WiFi.channel());
    Serial.print("ESP1 MAC: ");
    Serial.println(WiFi.macAddress());

    client.setInsecure();
    Serial.println("Telegram HTTPS READY");

    startNtp();
  } else {
    wifiWasConnected = false;
    Serial.println("WiFi connection timeout.");
    Serial.println("Fire detection will continue.");
  }
}

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.println();
      Serial.println("WiFi connected again!");
      Serial.print("IP: ");
      Serial.println(WiFi.localIP());
      client.setInsecure();
      startNtp();
    }
    // periodic NTP resync
    if (millis() - lastNtpSync >= NTP_RESYNC_INTERVAL) {
      startNtp();
    }
    return;
  }

  wifiWasConnected = false;

  if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
    lastWiFiAttempt = millis();
    Serial.println();
    Serial.println("WiFi disconnected. Retrying WiFi...");
    WiFi.disconnect();
    delay(50);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

// =====================================================================
// ESP-NOW (unchanged)
// =====================================================================

void sendFireData(bool fire, int angle) {
  FireData packet;
  packet.header = 0xAA;
  packet.fire = fire ? 1 : 0;
  packet.angle = constrain(angle, 0, 180);
  packet.packetID = ++packetID;

  uint8_t result = esp_now_send(ESP2_MAC, (uint8_t*)&packet, sizeof(packet));
  if (result != 0) {
    Serial.print("ESP-NOW SEND ERROR: ");
    Serial.println(result);
  }
}

// =====================================================================
// FLAME SENSOR - digital (unchanged)
// =====================================================================

bool flameDetected() {
  int lowCount = 0;
  for (int i = 0; i < 3; i++) {
    if (digitalRead(FLAME_SENSOR_GPIO) == LOW) lowCount++;
    delayMicroseconds(300);
  }
  return (lowCount >= 2);
}

// =====================================================================
// SERVO SCANNING (unchanged)
// =====================================================================

void scanForFire() {
  if (millis() - lastScanTime < SCAN_INTERVAL) return;
  lastScanTime = millis();

  scanServo.write(scanAngle);
  delay(2);

  bool flame = flameDetected();
  if (flame) {
    fireDetected = true;
    fireAngle = scanAngle;
    Serial.print("FIRE DETECTED AT ANGLE: ");
    Serial.println(fireAngle);
    return;
  }

  scanAngle += scanDirection * SCAN_STEP;
  if (scanAngle >= 180) {
    scanAngle = 180;
    scanDirection = -1;
  } else if (scanAngle <= 0) {
    scanAngle = 0;
    scanDirection = 1;
  }
}

// =====================================================================
// TELEGRAM (unchanged)
// =====================================================================

bool sendTelegramAlert() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Telegram NOT SENT: WiFi disconnected.");
    return false;
  }
  Serial.println();
  Serial.println("Sending Telegram FIRE ALERT...");

  String message;
  message += "FIRE ALERT!\n\n";
  message += "Fire detected.\n";
  message += "Direction: ";
  message += String(fireAngle);
  message += " degrees\n\n";
  message += "Smart Fire Extinguisher activated.";

  bool result = bot.sendMessage(CHAT_ID, message, "");
  Serial.println(result ? "Telegram alert SENT successfully." : "Telegram alert FAILED.");
  return result;
}

bool sendTelegramClear() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Telegram clear NOT SENT: WiFi disconnected.");
    return false;
  }
  Serial.println();
  Serial.println("Sending Telegram FIRE CLEARED...");
  bool result = bot.sendMessage(CHAT_ID, "Fire cleared.\nSmart Fire Extinguisher stopped.", "");
  Serial.println(result ? "Telegram clear message SENT." : "Telegram clear message FAILED.");
  return result;
}

void testTelegram() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Telegram test skipped: WiFi not connected.");
    return;
  }
  Serial.println();
  Serial.println("Testing Telegram...");
  bool result = bot.sendMessage(CHAT_ID, "Smart Fire Extinguisher ESP1 is ONLINE.", "");
  Serial.println(result ? "Telegram TEST SUCCESS." : "Telegram TEST FAILED.");
}

// =====================================================================
// SENSOR INIT
// =====================================================================

void initSensors() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

  bmeOK = bme.begin(0x76, &Wire);
  if (!bmeOK) {
    bmeOK = bme.begin(0x77, &Wire);
  }
  Serial.println(bmeOK ? "BME280: OK" : "BME280: NOT FOUND (check wiring/address)");

  adsOK = ads.begin(ADS1115_I2C_ADDR, &Wire);
  if (adsOK) {
    ads.setGain(ADS1115_GAIN);
    Serial.println("ADS1115: OK");
  } else {
    Serial.println("ADS1115: NOT FOUND (check wiring/address)");
  }
}

// =====================================================================
// FIREBASE INIT
// =====================================================================

void initFirebase() {
  fbConfig.host = FIREBASE_HOST;
  fbConfig.api_key = FIREBASE_API_KEY;
  fbAuth.user.email = FIREBASE_USER_EMAIL;
  fbAuth.user.password = FIREBASE_USER_PASSWORD;

  fbConfig.timeout.serverResponse = 5000; // ms, don't let a stuck call hang forever

  Firebase.begin(&fbConfig, &fbAuth);
  Firebase.reconnectWiFi(true);
  fbdo.setResponseSize(2048);

  firebaseReady = true;
  Serial.println("Firebase: initialized (auth/token handled in background)");
}

// =====================================================================
// SENSOR SAMPLING - fills one SensorSample, pushes into ring buffer
// =====================================================================

void collectSensorSample() {
  SensorSample s;
  memset(&s, 0, sizeof(s));

  s.uptimeMs = millis();
  uint32_t epoch = 0;
  getEpochIfSynced(epoch);
  s.epochTime = epoch;

  s.sensorsValid = true;

  // ---- BME280 ----
  if (bmeOK) {
    float t = bme.readTemperature();
    float h = bme.readHumidity();
    float p = bme.readPressure() / 100.0F;

    if (isnan(t) || isnan(h) || isnan(p)) {
      s.sensorsValid = false;
      Serial.println("BME280 read error: NaN");
    } else if (t < -40 || t > 85 || h < 0 || h > 100 || p < 300 || p > 1100) {
      s.sensorsValid = false;
      Serial.println("BME280 read error: out of range");
    } else {
      s.temperature = t;
      s.humidity = h;
      s.pressure = p;
    }
  } else {
    s.sensorsValid = false;
  }

  // ---- ADS1115: KY-026 analog + MQ-2 analog ----
  if (adsOK) {
    int16_t rawFlame = ads.readADC_SingleEnded(ADS1115_CHANNEL_FLAME);
    int16_t rawGas   = ads.readADC_SingleEnded(ADS1115_CHANNEL_GAS);

    if (rawFlame < 0 || rawGas < 0 || rawFlame > 32767 || rawGas > 32767) {
      s.sensorsValid = false;
      Serial.println("ADS1115 read error: out of range");
    } else {
      s.flameRaw = rawFlame;
      s.gasRaw = rawGas;
      s.flameVoltage = ads.computeVolts(rawFlame) / FLAME_DIVIDER_RATIO;
      s.gasVoltage   = ads.computeVolts(rawGas) / GAS_DIVIDER_RATIO;
    }
  } else {
    s.sensorsValid = false;
  }

  // ---- Digital flame + fire state label ----
  s.flameDigital = fireDetected ? 1 : 0;
  s.servoAngle = (uint8_t)(fireDetected ? fireAngle : scanAngle);

  bool mq2WarmedUp = (millis() > MQ2_WARMUP_MS);

  if (s.flameDigital) {
    s.fireState = STATE_FIRE;
  } else if (mq2WarmedUp && s.sensorsValid && s.gasRaw > GAS_WARNING_RAW_THRESHOLD) {
    s.fireState = STATE_WARNING;
  } else {
    s.fireState = STATE_NORMAL;
  }
  // PRE_FIRE / CRITICAL are reserved for future multi-sensor fusion logic
  // once enough labeled data has been collected - not auto-assigned yet.

  // ---- Push into ring buffer (non-blocking, just memory) ----
  if (bufCount >= SAMPLE_BUFFER_SIZE) {
    // Buffer full (Firebase/WiFi has been down for a while) - drop oldest.
    droppedSamples++;
    bufHead = (bufHead + 1) % SAMPLE_BUFFER_SIZE; // advance read start too
    bufCount--;
  }
  uint8_t writeIdx = (bufHead + bufCount) % SAMPLE_BUFFER_SIZE;
  sampleBuffer[writeIdx] = s;
  bufCount++;
}

// =====================================================================
// FIREBASE UPLOAD - sends ONE oldest buffered sample per call
// =====================================================================

bool uploadOldestSample() {
  if (bufCount == 0) return true; // nothing to do

  if (WiFi.status() != WL_CONNECTED) return false;
  if (!Firebase.ready()) return false;

  SensorSample &s = sampleBuffer[bufHead];

  char isoTime[25];
  bool haveIso = formatIsoTimestamp(s.epochTime, isoTime, sizeof(isoTime));

  FirebaseJson json;
  if (haveIso) json.set("timestamp", isoTime);
  json.set("uptime_ms", (double)s.uptimeMs);
  json.set("device_id", DEVICE_ID);
  json.set("experiment_id", EXPERIMENT_ID);
  json.set("temperature", s.temperature);
  json.set("humidity", s.humidity);
  json.set("pressure", s.pressure);
  json.set("flame_raw", s.flameRaw);
  json.set("flame_voltage", s.flameVoltage);
  json.set("gas_raw", s.gasRaw);
  json.set("gas_voltage", s.gasVoltage);
  json.set("fire_state", fireStateToStr(s.fireState));
  json.set("flame_digital", s.flameDigital);
  json.set("servo_angle", s.servoAngle);
  json.set("sensors_valid", s.sensorsValid);

  String path = String("/smart_fire_detection/devices/") + DEVICE_ID + "/readings";

  bool ok = Firebase.pushJSON(fbdo, path, json);

  if (ok) {
    bufHead = (bufHead + 1) % SAMPLE_BUFFER_SIZE;
    bufCount--;
  } else {
    Serial.print("Firebase upload FAILED: ");
    Serial.println(fbdo.errorReason());
  }
  return ok;
}

// =====================================================================
// SERIAL OUTPUT
// =====================================================================

void printSerialStatus(const SensorSample &s, bool uploaded) {
  Serial.println(F("========================================"));
  Serial.println(F("SMART FIRE DETECTION"));
  Serial.println(F("===================="));
  Serial.print(F("Temperature : ")); Serial.print(s.temperature, 2); Serial.println(F(" C"));
  Serial.print(F("Humidity    : ")); Serial.print(s.humidity, 2); Serial.println(F(" %"));
  Serial.print(F("Pressure    : ")); Serial.print(s.pressure, 2); Serial.println(F(" hPa"));
  Serial.println();
  Serial.print(F("Flame Raw   : ")); Serial.println(s.flameRaw);
  Serial.print(F("Flame Volt  : ")); Serial.print(s.flameVoltage, 3); Serial.println(F(" V"));
  Serial.println();
  Serial.print(F("Gas Raw     : ")); Serial.println(s.gasRaw);
  Serial.print(F("Gas Volt    : ")); Serial.print(s.gasVoltage, 3); Serial.println(F(" V"));
  Serial.println();
  Serial.print(F("Fire State  : ")); Serial.println(fireStateToStr(s.fireState));
  Serial.print(F("Firebase    : ")); Serial.println(uploaded ? F("UPLOADED") : F("QUEUED"));
  Serial.print(F("Buffer      : ")); Serial.print(bufCount); Serial.print("/"); Serial.println(SAMPLE_BUFFER_SIZE);
  if (droppedSamples > 0) {
    Serial.print(F("Dropped     : ")); Serial.println(droppedSamples);
  }
  Serial.println(F("========================================"));
}

// =====================================================================
// SETUP
// =====================================================================

void setup() {
  Serial.begin(115200);
  delay(200);
  systemStartMs = millis();

  Serial.println();
  Serial.println("================================");
  Serial.println(" SMART FIRE DETECTION ESP1");
  Serial.println("================================");

  pinMode(FLAME_SENSOR_GPIO, INPUT);

  scanServo.attach(SCAN_SERVO_GPIO);
  scanServo.write(90);
  delay(300);

  startWiFi();

  int channel = WiFi.channel();
  if (channel < 1 || channel > 13) {
    Serial.println("WARNING: Invalid WiFi channel. Using channel 6.");
    channel = 6;
  }
  Serial.print("ESP-NOW Channel: ");
  Serial.println(channel);

  wifi_set_channel(channel);

  Serial.println("Starting ESP-NOW...");
  if (esp_now_init() != 0) {
    Serial.println("ESP-NOW INIT FAILED");
    while (true) delay(1000);
  }
  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);

  if (esp_now_add_peer(ESP2_MAC, ESP_NOW_ROLE_SLAVE, channel, NULL, 0) != 0) {
    Serial.println("ESP2 peer add failed!");
  } else {
    Serial.println("ESP2 peer added successfully.");
  }

  Serial.println();
  Serial.println("ESP-NOW READY");

  initSensors();
  initFirebase();

  if (WiFi.status() == WL_CONNECTED) {
    testTelegram();
  } else {
    Serial.println("Telegram test skipped. WiFi is not connected.");
  }

  Serial.println();
  Serial.println("================================");
  Serial.println(" SYSTEM READY");
  Serial.println("================================");

  lastSampleTime = millis();
  lastUploadAttempt = millis();
}

// =====================================================================
// LOOP
// =====================================================================

void loop() {
  checkWiFi();

  // ---- Fire scanning / detection (unchanged, highest priority, fast) ----
  if (!fireDetected) {
    scanForFire();
  }

  if (fireDetected) {
    scanServo.write(fireAngle);

    if (millis() - lastSendTime >= SEND_INTERVAL) {
      lastSendTime = millis();
      sendFireData(true, fireAngle);
    }

    if (!previousFire) {
      previousFire = true;
      Serial.println();
      Serial.println("************************");
      Serial.println("       FIRE ACTIVE");
      Serial.print("       ANGLE: ");
      Serial.println(fireAngle);
      Serial.println("************************");

      if (WiFi.status() == WL_CONNECTED) {
        bool sent = sendTelegramAlert();
        lastTelegramTime = sent ? millis() : millis() - TELEGRAM_INTERVAL + 5000;
      } else {
        Serial.println("WiFi unavailable. Telegram will be retried.");
        lastTelegramTime = millis() - TELEGRAM_INTERVAL + 5000;
      }
    }

    if (millis() - lastTelegramTime >= TELEGRAM_INTERVAL) {
      if (WiFi.status() == WL_CONNECTED) {
        bool sent = sendTelegramAlert();
        if (sent) lastTelegramTime = millis();
      }
    }

    if (!flameDetected()) {
      delay(50);
      if (!flameDetected()) {
        fireDetected = false;
        Serial.println();
        Serial.println("Fire cleared.");

        for (int i = 0; i < 5; i++) {
          sendFireData(false, fireAngle);
          delay(20);
        }

        if (WiFi.status() == WL_CONNECTED) {
          sendTelegramClear();
        } else {
          Serial.println("WiFi unavailable. Fire clear Telegram not sent.");
        }

        previousFire = false;
        scanAngle = fireAngle;
        scanDirection = 1;
      }
    }
  } else {
    if (millis() - lastSendTime >= SEND_INTERVAL) {
      lastSendTime = millis();
      sendFireData(false, scanAngle);
    }
  }

  // ---- Sensor sampling: ~1 Hz, never blocks on network ----
  if (millis() - lastSampleTime >= SENSOR_SAMPLE_INTERVAL) {
    lastSampleTime = millis();
    collectSensorSample();
    printSerialStatus(sampleBuffer[(bufHead + bufCount - 1) % SAMPLE_BUFFER_SIZE], false);
  }

  // ---- Firebase upload: drains the queue, one sample per attempt.
  //      If a backlog exists, retry immediately instead of waiting the
  //      full interval, so the queue drains faster after an outage. ----
  bool dueForUpload = (millis() - lastUploadAttempt >= FIREBASE_UPLOAD_INTERVAL);
  bool backlog = (bufCount > 1);
  if (bufCount > 0 && (dueForUpload || backlog)) {
    lastUploadAttempt = millis();
    uploadOldestSample();
  }
}
