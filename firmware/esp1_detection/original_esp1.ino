// This file contains the original ESP1 firmware with Telegram and Servo integration.
// For the current data logging phase, esp1_detection.ino will be used.

#include <ESP8266WiFi.h>
#include <espnow.h>
#include <Servo.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>

extern "C" {
  #include "user_interface.h"
}

// ... [code truncated for brevity, refer to user request for full original ESP1 code] ...
