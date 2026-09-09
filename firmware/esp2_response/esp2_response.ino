#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Servo.h>

extern "C" {
  #include "user_interface.h"
}

// =====================================================
// GPIO
// =====================================================

#define AIM_SERVO_GPIO 12     // D6
#define RELAY_GPIO      5     // D1
#define BUZZER_GPIO     4     // D2
#define LED_GPIO       14     // D5

// =====================================================
// ESP-NOW CHANNEL
// =====================================================

#define WIFI_CHANNEL 6

// =====================================================
// RELAY
// =====================================================

// true  = Active LOW
// false = Active HIGH
#define RELAY_ACTIVE_LOW true

// =====================================================
// SERVO CALIBRATION
// =====================================================

// Servo physical limits
#define SERVO_MIN 5
#define SERVO_MAX 175

// Mechanical correction
#define SERVO_OFFSET 0

// Reverse servo direction if required
#define REVERSE_SERVO false

// =====================================================
// SERVO
// =====================================================

Servo aimServo;

// =====================================================
// ESP1 MAC
// =====================================================

uint8_t ESP1_MAC[] = {
  0xB4, 0x8A, 0x0A, 0xE3, 0xD2, 0x61
};

// =====================================================
// DATA
// =====================================================

struct FireData {
  uint8_t header;
  uint8_t fire;
  uint8_t angle;
  uint32_t packetID;
};

volatile bool packetAvailable = false;
volatile bool receivedFire = false;
volatile uint8_t receivedAngle = 90;
volatile uint32_t receivedID = 0;
volatile unsigned long lastPacketTime = 0;

// =====================================================
// SAFETY TIMEOUT
// =====================================================

#define SIGNAL_TIMEOUT 1000

// =====================================================
// CURRENT SERVO ANGLE
// =====================================================

int currentServoAngle = 90;

// =====================================================
// RELAY CONTROL
// =====================================================

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

// =====================================================
// FIRE ANGLE CONVERSION
// =====================================================

int convertAngle(int receivedAngle) {
  receivedAngle = constrain(receivedAngle, 0, 180);
  int outputAngle;

  if (REVERSE_SERVO) {
    outputAngle = 180 - receivedAngle;
  } else {
    outputAngle = receivedAngle;
  }

  outputAngle += SERVO_OFFSET;
  outputAngle = constrain(outputAngle, SERVO_MIN, SERVO_MAX);
  return outputAngle;
}

// =====================================================
// AIM SERVO
// =====================================================

void aimAtFire(int receivedAngle) {
  int servoAngle = convertAngle(receivedAngle);
  currentServoAngle = servoAngle;
  aimServo.write(servoAngle);

  Serial.print("ESP1 angle: ");
  Serial.print(receivedAngle);
  Serial.print(" -> ESP2 servo: ");
  Serial.println(servoAngle);
}

// =====================================================
// EXTINGUISHER CONTROL
// =====================================================

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
  Serial.println("EXTINGUISHER ON");
}

// =====================================================
// ESP-NOW RECEIVE CALLBACK
// =====================================================

void onDataReceive(uint8_t *mac, uint8_t *incomingData, uint8_t len) {
  if (len != sizeof(FireData)) return;

  if (memcmp(mac, ESP1_MAC, 6) != 0) return;

  FireData packet;
  memcpy(&packet, incomingData, sizeof(packet));

  if (packet.header != 0xAA) return;

  receivedFire = packet.fire;
  receivedAngle = packet.angle;
  receivedID = packet.packetID;
  lastPacketTime = millis();
  packetAvailable = true;
}

// =====================================================
// SETUP
// =====================================================

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(RELAY_GPIO, OUTPUT);
  pinMode(BUZZER_GPIO, OUTPUT);
  pinMode(LED_GPIO, OUTPUT);

  extinguisherOFF();

  aimServo.attach(AIM_SERVO_GPIO);
  aimServo.write(90);
  currentServoAngle = 90;
  delay(500);

  WiFi.mode(WIFI_STA);

  Serial.println("\n================================");
  Serial.println("SMART FIRE EXTINGUISHER ESP2");
  Serial.println("================================");
  Serial.print("ESP2 MAC: ");
  Serial.println(WiFi.macAddress());

  wifi_set_channel(WIFI_CHANNEL);
  Serial.print("Channel: ");
  Serial.println(WIFI_CHANNEL);

  if (esp_now_init() != 0) {
    Serial.println("ESP-NOW INIT FAILED");
    extinguisherOFF();
    while (true) delay(1000);
  }

  esp_now_set_self_role(ESP_NOW_ROLE_SLAVE);
  esp_now_register_recv_cb(onDataReceive);

  lastPacketTime = millis();
  extinguisherOFF();

  Serial.println("\nESP2 READY");
  Serial.println("Waiting for ESP1...");
}

// =====================================================
// LOOP
// =====================================================

void loop() {
  if (packetAvailable) {
    packetAvailable = false;

    if (receivedFire) {
      extinguisherON(receivedAngle);
      Serial.print("FIRE | RX Angle = ");
      Serial.println(receivedAngle);
    } else {
      extinguisherOFF();
      Serial.println("FIRE CLEARED");
    }
  }

  if (millis() - lastPacketTime > SIGNAL_TIMEOUT) {
    receivedFire = false;
    extinguisherOFF();
  }
}
