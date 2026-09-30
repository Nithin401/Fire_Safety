#pragma once
#include <math.h>

enum class FireStatus { SAFE, WARNING, HIGH_RISK, FIRE };

struct SensorReadings {
  float temperatureC = NAN;
  float humidityPercent = NAN;
  int gasRaw = 0;
  bool flameDetected = false;
  bool valid = false;
};

struct RiskAssessment {
  float filteredTemperatureC = NAN;
  float temperatureRateCPerMin = 0;
  float baselineTemperatureC = NAN;
  float baselineDeviationC = 0;
  int riskScore = 0;
  FireStatus status = FireStatus::SAFE;
  bool confirmed = false;
};

const char* statusName(FireStatus status);
