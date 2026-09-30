#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Servo.h>
#include <WiFiClientSecure.h>
#include <ESP8266HTTPClient.h>
#include <UniversalTelegramBot.h>

extern "C" {
  #include "user_interface.h"
}

// =====================================================
// WIFI / TELEGRAM / BACKEND CONFIGURATION
// =====================================================

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// IP Address of the laptop running the Python Backend Server
const char* BACKEND_URL   = "http://192.168.1.100:5000/api/telemetry";

#define BOT_TOKEN "YOUR_BOT_TOKEN"
#define CHAT_ID   "YOUR_CHAT_ID"

#define DEVICE_ID "dev_001"
#define ROOM_ID   "Kitchen"

WiFiClientSecure client;
UniversalTelegramBot bot(BOT_TOKEN, client);

// =====================================================
// PINS
// =====================================================

#define FLAME_SENSOR_GPIO 14     // D5
#define SCAN_SERVO_GPIO   12     // D6
#define FLAME_ANALOG_PIN  A0     // Analog pin for raw AI signal

// =====================================================
// ESP2 MAC
// =====================================================

uint8_t ESP2_MAC[] = {
  0x48, 0x3F, 0xDA, 0x5F, 0x0C, 0x55
};

// =====================================================
// ESP-NOW DATA
// =====================================================

struct FireData {
  uint8_t header;
  uint8_t fire;
  uint8_t angle;
  uint32_t packetID;
};

uint32_t packetID = 0;

// =====================================================
// SERVO & STATE
// =====================================================

Servo scanServo;

int scanAngle = 0;
int scanDirection = 1;
unsigned long lastScanTime = 0;

#define SCAN_INTERVAL 40
#define SCAN_STEP     3

bool fireDetected = false;
bool previousFire = false;
int fireAngle = 90;

// =====================================================
// TIMERS
// =====================================================

unsigned long lastSendTime = 0;
unsigned long lastTelegramTime = 0;
unsigned long lastWiFiAttempt = 0;
unsigned long lastTelemetryTime = 0;

#define SEND_INTERVAL        80
#define TELEGRAM_INTERVAL    30000
#define WIFI_RETRY_INTERVAL  10000
#define TELEMETRY_INTERVAL   2000    // Send telemetry to Python backend every 2s

bool wifiWasConnected = false;

// =====================================================
// START WIFI
// =====================================================

void startWiFi() {
  Serial.println("\nStarting WiFi...");
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
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("WiFi Channel: ");
    Serial.println(WiFi.channel());
    Serial.print("ESP1 MAC: ");
    Serial.println(WiFi.macAddress());

    client.setInsecure();
    Serial.println("Telegram HTTPS READY");
  } else {
    wifiWasConnected = false;
    Serial.println("WiFi connection timeout. Detection will continue offline.");
  }
}

// =====================================================
// WIFI RECONNECT
// =====================================================

void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.println("\nWiFi connected again!");
      client.setInsecure();
    }
    return;
  }

  wifiWasConnected = false;

  if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
    lastWiFiAttempt = millis();
    Serial.println("\nWiFi disconnected. Retrying...");
    WiFi.disconnect();
    delay(50);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

// =====================================================
// SEND ESP-NOW TO ESP2
// =====================================================

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

// =====================================================
// FLAME SENSOR SENSING
// =====================================================

bool flameDetected() {
  int lowCount = 0;
  for (int i = 0; i < 3; i++) {
    if (digitalRead(FLAME_SENSOR_GPIO) == LOW) {
      lowCount++;
    }
    delayMicroseconds(300);
  }
  return (lowCount >= 2);
}

// =====================================================
// SEND TELEMETRY TO PYTHON BACKEND & FIRESTORE
// =====================================================

void sendBackendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastTelemetryTime < TELEMETRY_INTERVAL) return;
  lastTelemetryTime = millis();

  int flameRaw = analogRead(FLAME_ANALOG_PIN);

  WiFiClient httpWiFiClient;
  HTTPClient http;

  if (http.begin(httpWiFiClient, BACKEND_URL)) {
    http.addHeader("Content-Type", "application/json");

    String jsonPayload = "{";
    jsonPayload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
    jsonPayload += "\"room_id\":\"" + String(ROOM_ID) + "\",";
    jsonPayload += "\"flame_raw\":" + String(flameRaw) + ",";
    jsonPayload += "\"fire_angle\":" + String(fireDetected ? fireAngle : scanAngle) + ",";
    jsonPayload += "\"is_fire\":" + String(fireDetected ? "true" : "false") + ",";
    jsonPayload += "\"temp_c\":25.4,";
    jsonPayload += "\"humidity\":56.2,";
    jsonPayload += "\"gas_raw\":130,";
    jsonPayload += "\"smoke_raw\":125,";
    jsonPayload += "\"esp_timestamp_ms\":" + String(millis());
    jsonPayload += "}";

    int httpCode = http.POST(jsonPayload);
    if (httpCode > 0) {
      Serial.printf("[HTTP] Telemetry POST result code: %d\n", httpCode);
    } else {
      Serial.printf("[HTTP] Telemetry POST failed, error: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  }
}

// =====================================================
// SERVO SCANNING
// =====================================================

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

// =====================================================
// TELEGRAM ALERT
// =====================================================

bool sendTelegramAlert() {
  if (WiFi.status() != WL_CONNECTED) return false;
  Serial.println("\nSending Telegram FIRE ALERT...");
  String message = "FIRE ALERT!\n\nFire detected.\nDirection: " + String(fireAngle) + " degrees\n\nSmart Fire Extinguisher activated.";
  return bot.sendMessage(CHAT_ID, message, "");
}

bool sendTelegramClear() {
  if (WiFi.status() != WL_CONNECTED) return false;
  Serial.println("\nSending Telegram FIRE CLEARED...");
  return bot.sendMessage(CHAT_ID, "Fire cleared.\nSmart Fire Extinguisher stopped.", "");
}

// =====================================================
// SETUP
// =====================================================

void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println("\n================================");
  Serial.println(" SMART FIRE EXTINGUISHER ESP1");
  Serial.println("================================");

  pinMode(FLAME_SENSOR_GPIO, INPUT);
  scanServo.attach(SCAN_SERVO_GPIO);
  scanServo.write(90);
  delay(300);

  startWiFi();

  int channel = WiFi.channel();
  if (channel < 1 || channel > 13) channel = 6;
  wifi_set_channel(channel);

  if (esp_now_init() != 0) {
    Serial.println("ESP-NOW INIT FAILED");
    while (true) delay(1000);
  }

  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
  esp_now_add_peer(ESP2_MAC, ESP_NOW_ROLE_SLAVE, channel, NULL, 0);

  Serial.println("\nESP-NOW & TELEMETRY SYSTEM READY");
}

// =====================================================
// LOOP
// =====================================================

void loop() {
  checkWiFi();
  sendBackendTelemetry(); // Sends real-time AI & Firestore telemetry payload

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
      Serial.println("\n************************\n       FIRE ACTIVE\n************************");
      if (WiFi.status() == WL_CONNECTED) sendTelegramAlert();
    }

    if (!flameDetected()) {
      delay(50);
      if (!flameDetected()) {
        fireDetected = false;
        Serial.println("\nFire cleared.");
        for (int i = 0; i < 5; i++) {
          sendFireData(false, fireAngle);
          delay(20);
        }
        if (WiFi.status() == WL_CONNECTED) sendTelegramClear();
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
}
