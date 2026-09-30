/**
 * FireShield AI — ESP32 Multi-Sensor Detection & Telemetry Node
 * 
 * Senses:
 * - Flame IR Analog (GPIO 35) & Digital (GPIO 27)
 * - Gas / Smoke MQ-2 Analog (GPIO 34)
 * - Temperature & Humidity DHT22 (GPIO 4)
 * - Sweeping Search Servo (GPIO 12)
 * 
 * Transmits:
 * - Structured Wi-Fi HTTP telemetry JSON to Python Backend / Firestore
 * - High-speed ESP-NOW binary packets to ESP2 Response Node
 */

#include <WiFi.h>
#include <esp_now.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ESP32Servo.h>
#include "../include/packet_contract.h"
#include "../include/detection_logic.h"

// =====================================================
// PINS & CONFIGURATION
// =====================================================
#define DHT_PIN             4       // DHT22 Data
#define DHT_TYPE            DHT22
#define MQ2_ANALOG_PIN      34      // ADC1_CH6 (Input-only)
#define FLAME_ANALOG_PIN    35      // ADC1_CH7 (Input-only)
#define FLAME_DIGITAL_PIN   27      // Digital flame interrupt/read
#define SCAN_SERVO_PIN      12      // PWM sweep servo

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* BACKEND_URL   = "http://192.168.1.100:5000/api/telemetry";

#define DEVICE_ID "dev_001"
#define ROOM_ID   "Kitchen"

uint8_t ESP2_MAC[] = { 0x48, 0x3F, 0xDA, 0x5F, 0x0C, 0x55 };

// =====================================================
// GLOBALS & OBJECTS
// =====================================================
DHT dht(DHT_PIN, DHT_TYPE);
Servo scanServo;
DetectionState flameState;

FireDataPacket currentPacket;
uint32_t packetCounter = 0;

int scanAngle = 90;
int scanDirection = 1;
unsigned long lastScanMs = 0;
unsigned long lastTelemetryMs = 0;
unsigned long lastDhtMs = 0;

float currentTemp = 24.5;
float currentHumidity = 55.0;
int currentGasRaw = 120;
int currentFlameRaw = 900;
bool fireConfirmed = false;
int confirmedFireAngle = 90;

void setup() {
    Serial.begin(115200);
    Serial.println("\n[INIT] FireShield AI Multi-Sensor ESP32 Starting...");
    
    pinMode(FLAME_DIGITAL_PIN, INPUT);
    init_detection_state(&flameState, 400, 3); // ADC threshold 400, 3 cycles persistence
    
    dht.begin();
    scanServo.attach(SCAN_SERVO_PIN);
    scanServo.write(scanAngle);
    
    // Wi-Fi Setup
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("[WIFI] Connecting");
    unsigned long wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 5000) {
        delay(200);
        Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WIFI] Offline mode active.");
    }
    
    // ESP-NOW Setup
    if (esp_now_init() == ESP_OK) {
        Serial.println("[ESPNOW] Initialized successfully.");
        esp_now_peer_info_t peerInfo = {};
        memcpy(peerInfo.peer_addr, ESP2_MAC, 6);
        peerInfo.channel = 0;
        peerInfo.encrypt = false;
        esp_now_add_peer(&peerInfo);
    } else {
        Serial.println("[ESPNOW] Init failed!");
    }
}

void loop() {
    unsigned long now = millis();
    
    // 1. Read DHT22 at 0.5 Hz
    if (now - lastDhtMs >= 2000) {
        lastDhtMs = now;
        float t = dht.readTemperature();
        float h = dht.readHumidity();
        if (!isnan(t)) currentTemp = t;
        if (!isnan(h)) currentHumidity = h;
    }
    
    // 2. Read Analogs
    currentFlameRaw = analogRead(FLAME_ANALOG_PIN) / 4; // Scale 12-bit (0-4095) down to 10-bit (0-1023)
    currentGasRaw   = analogRead(MQ2_ANALOG_PIN) / 4;
    
    // 3. Servo Sweep & Directional Scan
    if (now - lastScanMs >= 40) {
        lastScanMs = now;
        scanServo.write(scanAngle);
        
        bool flameCycle = evaluate_flame_detection(&flameState, currentFlameRaw);
        bool digitalFlame = (digitalRead(FLAME_DIGITAL_PIN) == LOW); // Active LOW
        
        if (flameCycle || digitalFlame) {
            fireConfirmed = true;
            confirmedFireAngle = scanAngle;
            Serial.printf("[FIRE CONFIRMED] Angle: %d deg | FlameRaw: %d | Gas: %d | Temp: %.1fC\n",
                          confirmedFireAngle, currentFlameRaw, currentGasRaw, currentTemp);
        } else {
            fireConfirmed = false;
        }
        
        scanAngle += scanDirection * 2;
        if (scanAngle >= 180) { scanAngle = 180; scanDirection = -1; }
        else if (scanAngle <= 0) { scanAngle = 0; scanDirection = 1; }
    }
    
    // 4. Send ESP-NOW Packet to ESP2
    currentPacket.header = PACKET_HEADER_MAGIC;
    currentPacket.fire = fireConfirmed ? 1 : 0;
    currentPacket.angle = (uint8_t)confirmedFireAngle;
    currentPacket.packetID = ++packetCounter;
    currentPacket.flameRaw = (uint16_t)currentFlameRaw;
    currentPacket.riskScore = calculate_flame_risk_score(currentFlameRaw, 400, flameState.current_persistence, 3);
    currentPacket.checksum = calculate_packet_checksum(&currentPacket);
    esp_now_send(ESP2_MAC, (uint8_t*)&currentPacket, sizeof(currentPacket));
    
    // 5. Send Telemetry JSON to Python Backend
    if (now - lastTelemetryMs >= 1000) {
        lastTelemetryMs = now;
        if (WiFi.status() == WL_CONNECTED) {
            HTTPClient http;
            if (http.begin(BACKEND_URL)) {
                http.addHeader("Content-Type", "application/json");
                http.addHeader("X-API-Key", "fireshield_local_dev_key_2026");
                
                String payload = "{";
                payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
                payload += "\"room_id\":\"" + String(ROOM_ID) + "\",";
                payload += "\"flame_raw\":" + String(currentFlameRaw) + ",";
                payload += "\"fire_angle\":" + String(fireConfirmed ? confirmedFireAngle : scanAngle) + ",";
                payload += "\"is_fire\":" + String(fireConfirmed ? "true" : "false") + ",";
                payload += "\"temp_c\":" + String(currentTemp, 2) + ",";
                payload += "\"humidity\":" + String(currentHumidity, 2) + ",";
                payload += "\"gas_raw\":" + String(currentGasRaw) + ",";
                payload += "\"smoke_raw\":" + String(currentGasRaw) + ",";
                payload += "\"esp_timestamp_ms\":" + String(now);
                payload += "}";
                
                http.POST(payload);
                http.end();
            }
        }
    }
}
