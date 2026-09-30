/* =====================================================================
   FIRESHIELD AI — ESP2 RESPONDER & EXTINGUISHER ACTUATOR NODE
   =====================================================================
   Platform: ESP8266 (NodeMCU 1.0 / WeMos D1 Mini / ESP-12E)
   Architecture: High-Speed Peer-to-Peer ESP-NOW Safety Slave
   
   Actuators & Interfaces:
     - D6 / GPIO12 : Nozzle Aiming Servo (0° to 180° bearing)
     - D1 / GPIO5  : Extinguisher Solenoid Relay / Water Pump
     - D2 / GPIO4  : High-Decibel Piezo Alarm Buzzer
     - D5 / GPIO14 : Strobe Alert LED Indicator

   Radio Link:
     - ESP-NOW: Receives high-speed FireDataPacket from ESP1 detector
     - Latency: < 10 ms (Local peer-to-peer radio, completely independent of WiFi/Cloud)
     - Safety Watchdog: Automatic 1500 ms signal-loss timeout shutoff
   ===================================================================== */

#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Servo.h>
#include "../include/packet_contract.h"

extern "C" {
  #include "user_interface.h"
}

// =====================================================================
// 1. PIN CONFIGURATION
// =====================================================================
#define AIM_SERVO_GPIO 12     // D6 / GPIO12
#define RELAY_GPIO      5     // D1 / GPIO5
#define BUZZER_GPIO     4     // D2 / GPIO4
#define LED_GPIO       14     // D5 / GPIO14

// Relay configuration: true = Active LOW (standard relay module), false = Active HIGH
#define RELAY_ACTIVE_LOW true

// Servo limits and calibration
#define SERVO_MIN   5
#define SERVO_MAX 175
#define SERVO_OFFSET 0
#define REVERSE_SERVO false

// Radio channel (must match ESP1 WiFi channel)
#define WIFI_CHANNEL 6

// Safety Timeout: Extinguisher shuts OFF if no fire signal received for 1500ms
#define SIGNAL_TIMEOUT_MS 1500

// Optional specific ESP1 MAC filter (set all 0x00 to accept from any trusted local ESP1)
uint8_t ESP1_MAC[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
bool MATCH_SPECIFIC_MAC = false;

// =====================================================================
// 2. STATE VARIABLES
// =====================================================================
Servo aimServo;
int currentServoAngle = 90;

volatile bool packetAvailable = false;
volatile bool receivedFire = false;
volatile uint8_t receivedAngle = 90;
volatile uint8_t receivedFireState = 0;
volatile uint8_t receivedRiskScore = 0;
char receivedZone[8] = "ZONE_1";
volatile uint32_t receivedID = 0;
volatile unsigned long lastPacketTime = 0;

// Legacy 7-byte struct for backward-compatibility fallback
struct LegacyFireData {
  uint8_t header;
  uint8_t fire;
  uint8_t angle;
  uint32_t packetID;
};

// =====================================================================
// 3. ACTUATOR CONTROLS
// =====================================================================

void relayOFF() {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(RELAY_GPIO, HIGH);
  } else {
    digitalWrite(RELAY_GPIO, LOW);
  }
}

void relayON() {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(RELAY_GPIO, LOW);
  } else {
    digitalWrite(RELAY_GPIO, HIGH);
  }
}

int convertAngle(int receivedAngle) {
  receivedAngle = constrain(receivedAngle, 0, 180);
  int outputAngle;

  if (REVERSE_SERVO) {
    outputAngle = 180 - receivedAngle;
  } else {
    outputAngle = receivedAngle;
  }

  outputAngle += SERVO_OFFSET;
  return constrain(outputAngle, SERVO_MIN, SERVO_MAX);
}

void aimAtFire(int angle) {
  int servoAngle = convertAngle(angle);
  currentServoAngle = servoAngle;
  aimServo.write(servoAngle);
}

void extinguisherOFF() {
  relayOFF();
  digitalWrite(BUZZER_GPIO, LOW);
  digitalWrite(LED_GPIO, LOW);
}

void extinguisherON(int angle) {
  aimAtFire(angle);
  relayON();
  digitalWrite(BUZZER_GPIO, HIGH);
  digitalWrite(LED_GPIO, HIGH);
  Serial.print(F(">>> EXTINGUISHER ACTIVE <<< Bearing: "));
  Serial.print(angle);
  Serial.print(F("° | Zone: "));
  Serial.println(receivedZone);
}

// =====================================================================
// 4. ESP-NOW RECEIVE CALLBACK
// =====================================================================

void onDataReceive(uint8_t *mac, uint8_t *incomingData, uint8_t len) {
  if (MATCH_SPECIFIC_MAC) {
    if (memcmp(mac, ESP1_MAC, 6) != 0) return;
  }

  // 1. Unified 18-byte FireDataPacket
  if (len == sizeof(FireDataPacket)) {
    FireDataPacket pkt;
    memcpy(&pkt, incomingData, sizeof(pkt));

    if (validate_packet(&pkt)) {
      receivedFire = (pkt.fire == 1);
      receivedAngle = pkt.angle;
      receivedID = pkt.packetID;
      receivedFireState = pkt.fireState;
      receivedRiskScore = pkt.riskScore;
      strncpy(receivedZone, pkt.zoneId, sizeof(receivedZone) - 1);
      receivedZone[sizeof(receivedZone) - 1] = '\0';
      lastPacketTime = millis();
      packetAvailable = true;
    }
    return;
  }

  // 2. Legacy 7-byte fallback
  if (len == sizeof(LegacyFireData)) {
    LegacyFireData legacyPkt;
    memcpy(&legacyPkt, incomingData, sizeof(legacyPkt));
    if (legacyPkt.header == PACKET_HEADER_MAGIC) {
      receivedFire = (legacyPkt.fire == 1);
      receivedAngle = legacyPkt.angle;
      receivedID = legacyPkt.packetID;
      lastPacketTime = millis();
      packetAvailable = true;
    }
  }
}

// =====================================================================
// 5. SETUP
// =====================================================================

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F(" FIRESHIELD AI — ESP2 RESPONDER NODE"));
  Serial.println(F("========================================"));

  pinMode(RELAY_GPIO, OUTPUT);
  pinMode(BUZZER_GPIO, OUTPUT);
  pinMode(LED_GPIO, OUTPUT);

  extinguisherOFF();

  aimServo.attach(AIM_SERVO_GPIO);
  aimServo.write(currentServoAngle);
  delay(300);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  wifi_set_channel(WIFI_CHANNEL);

  Serial.print(F("ESP2 MAC Address: "));
  Serial.println(WiFi.macAddress());

  if (esp_now_init() != 0) {
    Serial.println(F("ESP-NOW init failed!"));
    return;
  }

  esp_now_set_self_role(ESP_NOW_ROLE_SLAVE);
  esp_now_register_recv_cb(onDataReceive);

  Serial.println(F("ESP-NOW Slave Listening for Fire Triggers..."));
  Serial.println(F("========================================\n"));
}

// =====================================================================
// 6. MAIN LOOP
// =====================================================================

void loop() {
  // Check if a packet was received
  if (packetAvailable) {
    packetAvailable = false;

    if (receivedFire) {
      extinguisherON(receivedAngle);
    } else {
      extinguisherOFF();
      aimAtFire(receivedAngle);
    }
  }

  // Safety Watchdog: If no packets received within timeout, shut OFF actuator
  if (millis() - lastPacketTime > SIGNAL_TIMEOUT_MS) {
    extinguisherOFF();
  }

  delay(20);
}
