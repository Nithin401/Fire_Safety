#include <Arduino.h>
#include "config.h"
#include "temperature_detector.h"

namespace {
int severity(FireStatus status) { return static_cast<int>(status); }

FireStatus provisionalStatus(float temperature, float rate) {
  if (temperature >= config::FIRE_TEMPERATURE_C || rate >= config::FIRE_RATE_C_PER_MIN) return FireStatus::FIRE;
  if (temperature >= config::HIGH_RISK_TEMPERATURE_C || rate >= config::HIGH_RISK_RATE_C_PER_MIN) return FireStatus::HIGH_RISK;
  if (temperature >= config::WARNING_TEMPERATURE_C || rate >= config::WARNING_RATE_C_PER_MIN) return FireStatus::WARNING;
  return FireStatus::SAFE;
}

int riskScore(float temperature, float rate) {
  const float absolute = constrain((temperature - 25.0F) / 45.0F * 60.0F, 0.0F, 60.0F);
  const float trend = constrain(rate / config::FIRE_RATE_C_PER_MIN * 40.0F, 0.0F, 40.0F);
  return static_cast<int>(constrain(absolute + trend, 0.0F, 100.0F));
}
}

RiskAssessment TemperatureDetector::update(float temperatureC, unsigned long nowMs) {
  RiskAssessment result;
  if (!initialized_) {
    initialized_ = true; filtered_ = previousFiltered_ = baseline_ = temperatureC; previousMs_ = nowMs;
  }
  const unsigned long elapsed = nowMs - previousMs_;
  filtered_ = config::EMA_ALPHA * temperatureC + (1.0F - config::EMA_ALPHA) * filtered_;
  const float rate = elapsed > 0 ? (filtered_ - previousFiltered_) * 60000.0F / elapsed : 0.0F;
  const FireStatus proposed = provisionalStatus(filtered_, rate);
  if (proposed == FireStatus::SAFE) {
    candidate_ = FireStatus::SAFE; candidateSinceMs_ = 0;
    baseline_ = 0.02F * filtered_ + 0.98F * baseline_; // only learn during normal conditions
  } else if (proposed != candidate_) {
    candidate_ = proposed; candidateSinceMs_ = nowMs;
  }
  const bool confirmed = proposed == FireStatus::SAFE || (nowMs - candidateSinceMs_ >= config::CONFIRMATION_DURATION_MS);
  result.filteredTemperatureC = filtered_;
  result.temperatureRateCPerMin = rate;
  result.baselineTemperatureC = baseline_;
  result.baselineDeviationC = filtered_ - baseline_;
  result.riskScore = riskScore(filtered_, rate);
  result.status = confirmed ? proposed : FireStatus::SAFE;
  result.confirmed = confirmed;
  previousFiltered_ = filtered_; previousMs_ = nowMs;
  return result;
}
