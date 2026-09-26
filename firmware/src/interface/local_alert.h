#pragma once
#include "system_types.h"

class LocalAlert {
 public:
  void begin();
  void render(const SensorReadings& readings, const RiskAssessment& assessment);
};
