#pragma once
#include "system_types.h"

class TemperatureDetector {
 public:
  RiskAssessment update(float temperatureC, unsigned long nowMs);

 private:
  bool initialized_ = false;
  float filtered_ = 0;
  float previousFiltered_ = 0;
  float baseline_ = 0;
  unsigned long previousMs_ = 0;
  unsigned long candidateSinceMs_ = 0;
  FireStatus candidate_ = FireStatus::SAFE;
};
