#include <ESP8266WiFi.h>
#include <espnow.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Servo.h>
#include <DHT.h>

#include "secrets.h"

// =============== CREDENTIALS ===============
// Values are loaded from secrets.h (which is git-ignored).
// You can edit them in secrets.h or directly replace them here.
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* thingSpeakAPIKey = THINGSPEAK_WRITE_API_KEY;

// =============== GPIO PINS ===============
#define FLAME_AO A0
#define SMOKE_DO 12
#define DHT_PIN 4
#define SERVO_PIN 14
#define DHT_TYPE DHT11

// Calibrate using your sensor's actual readings.
const int FLAME_THRESHOLD = 600;
const int SMOKE_ACTIVE_STATE = LOW;

// Receiver MAC: 48:3F:DA:5F:0C:55
uint8_t receiverMAC[] = {
  0x48, 0x3F, 0xDA, 0x5F, 0x0C, 0x55
};

// =============== COMPONENTS ===============
DHT dht(DHT_PIN, DHT_TYPE);
Servo fireServo;

// =============== SENSOR VARIABLES ===============
int flameValue = 0;
int smokeStatus = HIGH;
float temperature = 0.0;
float humidity = 0.0;
int servoAngle = 0;
int servoDirection = 1;
bool fireDetected = false;

// =============== TIMERS ===============
unsigned long lastServoMove = 0;
unsigned long lastSensorRead = 0;
unsigned long lastESPNowSend = 0;
unsigned long lastThingSpeak = 0;

const unsigned long SERVO_INTERVAL = 80;
const unsigned long SENSOR_INTERVAL = 2000;
const unsigned long ESP_NOW_INTERVAL = 200;
const unsigned long THINGSPEAK_INTERVAL = 16000;

// =============== ESP-NOW DATA ===============
struct struct_message {
  bool fireDetected;
  int servoAngle;
  int flameValue;
  int smokeStatus;
  float temperature;
  float humidity;
};

struct_message dataToSend;

// =============== ESP-NOW CALLBACK ===============
void OnDataSent(uint8_t *mac_addr, uint8_t sendStatus) {
  Serial.print("ESP-NOW: ");
  Serial.println(sendStatus == 0 ? "SUCCESS" : "FAILED");
}

// =============== READ SENSORS ===============
void readSensors() {
  flameValue = analogRead(FLAME_AO);
  smokeStatus = digitalRead(SMOKE_DO);

  float newTemperature = dht.readTemperature();
  float newHumidity = dht.readHumidity();

  if (!isnan(newTemperature)) {
    temperature = newTemperature;
  } else {
    Serial.println("DHT11 temperature read failed");
  }

  if (!isnan(newHumidity)) {
    humidity = newHumidity;
  } else {
    Serial.println("DHT11 humidity read failed");
  }

  bool flameDetected = (flameValue < FLAME_THRESHOLD);
  bool smokeDetected = (smokeStatus == SMOKE_ACTIVE_STATE);

  // Fire status is active if either sensor detects a hazard.
  fireDetected = flameDetected || smokeDetected;

  Serial.println("\n-------- SENSOR DATA --------");
  Serial.print("Flame value: ");
  Serial.println(flameValue);

  Serial.print("Smoke status: ");
  Serial.println(smokeDetected ? "DETECTED" : "NOT DETECTED");

  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" C");

  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print("Fire status: ");
  Serial.println(fireDetected ? "DETECTED" : "NORMAL");

  Serial.print("Servo angle: ");
  Serial.println(servoAngle);
  Serial.println("-----------------------------");
}

// =============== SERVO SCANNING ===============
void controlServo() {
  if (fireDetected) {
    // Hold the current angle when a hazard is detected.
    fireServo.write(servoAngle);
    return;
  }

  if (millis() - lastServoMove >= SERVO_INTERVAL) {
    lastServoMove = millis();

    servoAngle += servoDirection;

    if (servoAngle >= 180) {
      servoAngle = 180;
      servoDirection = -1;
    } else if (servoAngle <= 0) {
      servoAngle = 0;
      servoDirection = 1;
    }

    fireServo.write(servoAngle);
  }
}

// =============== SEND ESP-NOW DATA ===============
void sendESPNowData() {
  dataToSend.fireDetected = fireDetected;
  dataToSend.servoAngle = servoAngle;
  dataToSend.flameValue = flameValue;
  dataToSend.smokeStatus = smokeStatus;
  dataToSend.temperature = temperature;
  dataToSend.humidity = humidity;

  uint8_t result = esp_now_send(
    receiverMAC,
    (uint8_t*)&dataToSend,
    sizeof(dataToSend)
  );

  if (result != 0) {
    Serial.println("ESP-NOW send request failed");
  }
}

// =============== THINGSPEAK: SIX FIELDS ===============
void sendToThingSpeak() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected; ThingSpeak upload skipped");
    return;
  }

  WiFiClient client;
  HTTPClient http;

  String url = "http://api.thingspeak.com/update?api_key=";
  url += thingSpeakAPIKey;

  // Field 1: Flame analog value
  url += "&field1=" + String(flameValue);

  // Field 2: Smoke status (1 = detected)
  url += "&field2=";
  url += String(smokeStatus == SMOKE_ACTIVE_STATE ? 1 : 0);

  // Field 3: Temperature
  url += "&field3=" + String(temperature, 2);

  // Field 4: Humidity
  url += "&field4=" + String(humidity, 2);

  // Field 5: Servo angle
  url += "&field5=" + String(servoAngle);

  // Field 6: Fire status (1 = flame or smoke detected)
  url += "&field6=";
  url += String(fireDetected ? 1 : 0);

  Serial.println("Uploading 6 fields to ThingSpeak...");

  http.setTimeout(5000);

  if (http.begin(client, url)) {
    int httpCode = http.GET();

    if (httpCode > 0) {
      String response = http.getString();

      Serial.print("HTTP response: ");
      Serial.println(httpCode);

      Serial.print("ThingSpeak entry ID: ");
      Serial.println(response);

      if (response.toInt() > 0) {
        Serial.println("ThingSpeak upload successful");
      } else {
        Serial.println("Upload rejected. Check API key and channel.");
      }
    } else {
      Serial.print("ThingSpeak error: ");
      Serial.println(http.errorToString(httpCode));
    }

    http.end();
  } else {
    Serial.println("Could not start HTTP request");
  }
}

// =============== SETUP ===============
void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(SMOKE_DO, INPUT);

  dht.begin();

  fireServo.attach(SERVO_PIN);
  fireServo.write(servoAngle);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("Transmitter MAC: ");
  Serial.println(WiFi.macAddress());

  Serial.print("WiFi channel: ");
  Serial.println(WiFi.channel());

  if (esp_now_init() != 0) {
    Serial.println("ESP-NOW initialization failed");
    return;
  }

  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
  esp_now_register_send_cb(OnDataSent);

  if (esp_now_add_peer(
        receiverMAC,
        ESP_NOW_ROLE_SLAVE,
        0,
        NULL,
        0
      ) != 0) {
    Serial.println("Failed to add receiver peer");
  } else {
    Serial.println("ESP-NOW initialized");
  }

  // Take an initial reading before the first transmission.
  readSensors();

  Serial.println("TRANSMITTER READY");
}

// =============== MAIN LOOP ===============
void loop() {
  unsigned long now = millis();

  if (now - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = now;
    readSensors();
  }

  controlServo();

  if (now - lastESPNowSend >= ESP_NOW_INTERVAL) {
    lastESPNowSend = now;
    sendESPNowData();
  }

  if (now - lastThingSpeak >= THINGSPEAK_INTERVAL) {
    lastThingSpeak = now;
    sendToThingSpeak();
  }

  delay(5);
}
