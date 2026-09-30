#pragma once
#include <Arduino.h>
#include "system_types.h"

class Telemetry {
 public:
  void begin();
  void maintainConnection();
  void publishSerial(const SensorReadings& readings, const RiskAssessment& assessment) const;
  void publishMqtt(const SensorReadings& readings, const RiskAssessment& assessment);
};
