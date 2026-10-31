from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from services.baseline_service import BaselineService


class RiskState:
    NORMAL = "NORMAL"
    BASELINE_ANOMALY = "BASELINE_ANOMALY"
    EARLY_WARNING = "EARLY_WARNING"
    SINGLE_SENSOR_SUSPECT = "SINGLE_SENSOR_SUSPECT"
    DUAL_SENSOR_ALERT = "DUAL_SENSOR_ALERT"
    CONFIRMED_FIRE_ALERT = "CONFIRMED_FIRE_ALERT"
    HARDWARE_FIRE_ALERT = "HARDWARE_FIRE_ALERT"
    SENSOR_OR_DATA_FAULT = "SENSOR_OR_DATA_FAULT"


class RiskEngine:
    """Room-adaptive fire risk evaluation engine.
    
    Evaluates ThingSpeak readings against:
    1. Priority 1: Hardware-rule fire alarm (field6 == 1, or flame < 600 or smoke == 0).
    2. Priority 2: Multi-indicator early warning (temperature rise rate, baseline deviation, optical flame drop).
    3. Priority 3: Room environmental baseline anomaly (statistical z-score / sigma deviation).
    4. Data quality & fault detection (stale data, missing fields, out-of-range sensor values).
    """

    def __init__(self, config=None, baseline_service: Optional[BaselineService] = None):
        self.config = config or Config
        self.baseline_service = baseline_service or BaselineService(config=self.config)
        
        # Thresholds
        self.temp_rise_threshold = getattr(self.config, "EARLY_WARNING_TEMP_RISE_RATE_C_PER_MIN", 1.5)
        self.anomaly_sigma_threshold = getattr(self.config, "BASELINE_ANOMALY_SIGMA_THRESHOLD", 2.5)
        self.early_warning_cooldown = getattr(self.config, "COOLDOWN_SECONDS_EARLY_WARNING", 300)
        self.anomaly_cooldown = getattr(self.config, "COOLDOWN_SECONDS_ANOMALY", 600)
        self.all_clear_consecutive_needed = getattr(self.config, "ALL_CLEAR_CONSECUTIVE_READINGS", 3)

        # State tracking (sliding window for rate of change, cooldowns, last state)
        self.current_state: str = RiskState.NORMAL
        self.previous_state: str = RiskState.NORMAL
        self.consecutive_normal_readings: int = 0
        self.hazard_active: bool = False
        self.last_hazard_state: Optional[str] = None
        self.last_hardware_alert_time: Optional[datetime] = None
        self.last_early_warning_time: Optional[datetime] = None
        self.last_anomaly_time: Optional[datetime] = None
        
        # Recent readings buffer for rate of change: list of (timestamp_dt, temp_c)
        self._temp_history: List[Tuple[datetime, float]] = []

    def evaluate_reading(
        self,
        reading: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate a single ThingSpeak reading and determine the risk state and any triggered event."""
        active_baseline = baseline or self.baseline_service.get_baseline()
        now_utc = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. Check Data Validity & Freshness (SENSOR_OR_DATA_FAULT)
        # -------------------------------------------------------------
        if not reading or reading.get("is_stale", False):
            age_sec = reading.get("age_seconds") if reading else None
            fault_reason = f"Telemetry stream is stale ({age_sec:.1f}s since last update, threshold: 60s)" if age_sec else "No telemetry received"
            self.previous_state = self.current_state
            self.current_state = RiskState.SENSOR_OR_DATA_FAULT
            self.consecutive_normal_readings = 0
            return {
                "state": RiskState.SENSOR_OR_DATA_FAULT,
                "severity": "WARNING",
                "should_alert": self.previous_state != RiskState.SENSOR_OR_DATA_FAULT,
                "reason": fault_reason,
                "metrics": self._empty_metrics(reading),
            }

        temp_c = reading.get("temperature_c")
        hum_pct = reading.get("humidity_pct")
        flame_raw = reading.get("flame_raw")
        smoke_status = reading.get("smoke_status")
        fire_status = reading.get("fire_status")
        entry_id = reading.get("entry_id")

        if temp_c is None or hum_pct is None or flame_raw is None or smoke_status is None:
            self.previous_state = self.current_state
            self.current_state = RiskState.SENSOR_OR_DATA_FAULT
            self.consecutive_normal_readings = 0
            return {
                "state": RiskState.SENSOR_OR_DATA_FAULT,
                "severity": "WARNING",
                "should_alert": self.previous_state != RiskState.SENSOR_OR_DATA_FAULT,
                "reason": "Missing required sensor fields in telemetry record",
                "metrics": self._empty_metrics(reading),
            }

        # -------------------------------------------------------------
        # Update Rate of Change History
        # -------------------------------------------------------------
        created_at_dt = self._parse_iso_time(reading.get("created_at")) or now_utc
        self._record_temp_history(created_at_dt, float(temp_c))
        temp_rate_c_min = self._calculate_temp_rise_rate()

        # Baseline Deviation
        # Baseline Deviations (Temperature & Humidity)
        temp_dev = None
        hum_dev = None
        base_temp_mean = None
        base_hum_mean = None
        is_temp_anomalous = False
        is_hum_dropping = False
        if active_baseline:
            base_temp_mean = active_baseline.get("temperature_mean")
            base_hum_mean = active_baseline.get("humidity_mean")
            temp_std = active_baseline.get("temperature_std", 1.0)
            hum_std = active_baseline.get("humidity_std", 5.0)
            if base_temp_mean is not None:
                temp_dev = float(temp_c) - float(base_temp_mean)
                if temp_std and temp_std > 0:
                    z_score = abs(temp_dev) / temp_std
                    is_temp_anomalous = z_score >= self.anomaly_sigma_threshold
            if base_hum_mean is not None:
                hum_dev = float(hum_pct) - float(base_hum_mean)
                # Physical combustion signature: relative humidity decreases as fire dries the air
                if hum_std and hum_std > 0:
                    is_hum_dropping = hum_dev <= -1.0 * hum_std

        # Absolute dry air check (combustion drying)
        if not is_hum_dropping and hum_pct < 35.0:
            is_hum_dropping = True

        is_temp_rising = (
            (temp_rate_c_min is not None and temp_rate_c_min >= self.temp_rise_threshold)
            or (temp_dev is not None and temp_dev >= 2.0)
        )

        # -------------------------------------------------------------
        # Multi-Sensor State & Confidence Evaluation
        # -------------------------------------------------------------
        flame_active = flame_raw is not None and flame_raw < 600
        smoke_active = smoke_status is not None and smoke_status == 1
        dual_sensor_active = flame_active and smoke_active
        single_sensor_active = flame_active != smoke_active

        # Multi-Sensor Confidence Calculation (0 - 100%)
        # 1. Optical Flame: +35% if < 600, +15% if < 800
        # 2. Smoke Detector: +35% if active (== 1)
        # 3. Temperature Rise: +15% if rate-of-rise >= 1.5°C/min or temp elevated
        # 4. Humidity Decrease: +15% if humidity dropped below normal baseline
        confidence_score = 0
        if flame_raw is not None:
            if flame_raw < 600:
                confidence_score += 35
            elif flame_raw < 800:
                confidence_score += 15
        if smoke_active:
            confidence_score += 35
        if is_temp_rising:
            confidence_score += 15
        if is_hum_dropping:
            confidence_score += 15

        confidence_score = min(100, confidence_score)

        should_phone_call = False
        fire_state: Optional[str] = None
        severity: str = "NORMAL"
        reason_str: str = ""

        # Tier 1: Dual-Sensor Confirmation (Both Flame AND Smoke Active)
        if dual_sensor_active:
            should_phone_call = True
            self.hazard_active = True
            self.consecutive_normal_readings = 0

            if is_temp_rising or is_hum_dropping:
                fire_state = RiskState.CONFIRMED_FIRE_ALERT
                severity = "CRITICAL"
                self.last_hazard_state = RiskState.CONFIRMED_FIRE_ALERT
                reasons = [
                    f"Confirmed Fire: Both Flame ({flame_raw:.0f} < 600) and Smoke detectors active"
                ]
                if is_temp_rising:
                    reasons.append(f"Temperature rising (+{temp_rate_c_min or 0:.2f} °C/min)")
                if is_hum_dropping:
                    reasons.append(f"Combustion humidity drop ({hum_pct:.1f}%)")
                reasons.append(f"Multi-sensor confidence: {confidence_score}%")
                reason_str = " | ".join(reasons)
            else:
                fire_state = RiskState.DUAL_SENSOR_ALERT
                severity = "CRITICAL"
                self.last_hazard_state = RiskState.DUAL_SENSOR_ALERT
                reason_str = (
                    f"Dual-Sensor Fire Alert: Both Flame ({flame_raw:.0f} < 600) and Smoke detectors active. "
                    f"Multi-sensor confidence: {confidence_score}%. High priority phone call queued."
                )

        # Tier 2: Single Sensor Trigger with Physical Verification (Flame OR Smoke + Temp Rise + Humidity Drop)
        elif single_sensor_active and is_temp_rising and is_hum_dropping:
            should_phone_call = True
            self.hazard_active = True
            self.consecutive_normal_readings = 0
            fire_state = RiskState.CONFIRMED_FIRE_ALERT
            severity = "CRITICAL"
            self.last_hazard_state = RiskState.CONFIRMED_FIRE_ALERT
            sensor_name = "Flame sensor" if flame_active else "Smoke detector"
            reason_str = (
                f"Multi-Sensor Fire: {sensor_name} trigger verified by rapid temperature rise "
                f"(+{temp_rate_c_min or 0:.2f} °C/min) and combustion humidity drop ({hum_pct:.1f}%). "
                f"Confidence: {confidence_score}%."
            )

        # Tier 3: Single Sensor Trigger WITHOUT Physical Verification (SUSPECTED FALSE ALARM)
        elif single_sensor_active:
            should_phone_call = False  # DO NOT place phone call for single sensor false alarms
            self.hazard_active = True
            self.consecutive_normal_readings = 0
            fire_state = RiskState.SINGLE_SENSOR_SUSPECT
            severity = "WARNING"
            self.last_hazard_state = RiskState.SINGLE_SENSOR_SUSPECT
            sensor_name = "Flame sensor" if flame_active else "Smoke detector"
            reason_str = (
                f"Suspected False Alarm: Single sensor reacting ({sensor_name}) without dual-sensor confirmation. "
                f"Ambient humidity ({hum_pct:.1f}%) and temperature ({temp_c:.1f} °C) remain within normal bounds. "
                f"Confidence: {confidence_score}%. Phone call withheld to prevent false alarm."
            )

        # Tier 4: Hardware Rule Flag (field6 == 1) on legacy/unclassified readings
        elif fire_status == 1:
            if is_temp_rising or is_hum_dropping:
                should_phone_call = True
                fire_state = RiskState.CONFIRMED_FIRE_ALERT
                severity = "CRITICAL"
                reason_str = f"Hardware fire flag (field6=1) verified by combustion temperature/humidity drop. Confidence: {confidence_score}%."
            else:
                should_phone_call = False
                fire_state = RiskState.SINGLE_SENSOR_SUSPECT
                severity = "WARNING"
                reason_str = (
                    f"Hardware rule triggered (field6=1) without dual-sensor confirmation. "
                    f"Ambient humidity ({hum_pct:.1f}%) and temperature ({temp_c:.1f} °C) are normal. "
                    f"Suspected false alarm; phone call withheld."
                )

        metrics = {
            "entry_id": entry_id,
            "temperature_c": temp_c,
            "humidity_pct": hum_pct,
            "flame_raw": flame_raw,
            "smoke_status": smoke_status,
            "fire_status": fire_status,
            "servo_angle": reading.get("servo_angle"),
            "baseline_temp_mean": base_temp_mean,
            "baseline_hum_mean": base_hum_mean,
            "temp_deviation": temp_dev,
            "hum_deviation": hum_dev,
            "temp_rate_c_min": temp_rate_c_min,
            "is_temp_anomalous": is_temp_anomalous,
            "is_temp_rising": is_temp_rising,
            "is_hum_dropping": is_hum_dropping,
            "flame_detected": flame_active,
            "smoke_detected": smoke_active,
            "dual_sensor_confirmed": dual_sensor_active,
            "single_sensor_suspect": single_sensor_active and not (is_temp_rising and is_hum_dropping),
            "confidence_score": confidence_score,
            "should_phone_call": should_phone_call,
        }

        # If any of the above fire states fired, return the evaluation
        if fire_state:
            self.previous_state = self.current_state
            self.current_state = fire_state

            # Avoid repeat alert spam within 60s if state unchanged
            should_alert = True
            if self.previous_state == fire_state and self.last_hardware_alert_time:
                elapsed = (now_utc - self.last_hardware_alert_time).total_seconds()
                if elapsed < 60:
                    should_alert = False

            if should_alert:
                self.last_hardware_alert_time = now_utc

            return {
                "state": fire_state,
                "event_type": fire_state,
                "severity": severity,
                "should_alert": should_alert,
                "should_phone_call": should_phone_call,
                "reason": reason_str,
                "metrics": metrics,
            }

        # -------------------------------------------------------------
        # Priority 2: Multi-Indicator Early Warning
        # -------------------------------------------------------------
        is_rapid_rise = temp_rate_c_min is not None and temp_rate_c_min >= self.temp_rise_threshold
        # Optical flame dropping near threshold (e.g. 600 to 800) indicates elevated thermal/IR radiation
        is_flame_approaching = flame_raw < 800
        # High temperature deviation with low humidity (combustion drying)
        is_thermal_threat = (temp_dev is not None and temp_dev >= 4.0) or (is_temp_anomalous and hum_pct < 35.0)

        is_early_warning = is_rapid_rise or (is_flame_approaching and temp_dev is not None and temp_dev > 2.0) or (is_thermal_threat and is_rapid_rise)

        if is_early_warning:
            self.previous_state = self.current_state
            self.current_state = RiskState.EARLY_WARNING
            self.hazard_active = True
            self.last_hazard_state = RiskState.EARLY_WARNING
            self.consecutive_normal_readings = 0

            warning_reasons = []
            if is_rapid_rise:
                warning_reasons.append(f"Rapid temperature rise (+{temp_rate_c_min:.2f} °C/min)")
            if is_flame_approaching:
                warning_reasons.append(f"Elevated infrared emission (flame A0: {flame_raw:.0f})")
            if is_thermal_threat:
                warning_reasons.append(f"Severe thermal deviation (+{temp_dev:.1f} °C above room baseline)")
            reason_str = "Early warning: " + " & ".join(warning_reasons)

            # Apply cooldown for early warning
            should_alert = True
            if self.last_early_warning_time:
                elapsed = (now_utc - self.last_early_warning_time).total_seconds()
                if elapsed < self.early_warning_cooldown:
                    should_alert = False

            if should_alert:
                self.last_early_warning_time = now_utc

            return {
                "state": RiskState.EARLY_WARNING,
                "event_type": RiskState.EARLY_WARNING,
                "severity": "HIGH",
                "should_alert": should_alert,
                "reason": reason_str,
                "metrics": metrics,
            }

        # -------------------------------------------------------------
        # Priority 3: Room-Baseline Anomaly (Environmental Only)
        # -------------------------------------------------------------
        if is_temp_anomalous and temp_dev is not None:
            self.previous_state = self.current_state
            self.current_state = RiskState.BASELINE_ANOMALY
            self.hazard_active = True
            self.last_hazard_state = RiskState.BASELINE_ANOMALY
            self.consecutive_normal_readings = 0

            reason_str = (
                f"Environmental baseline anomaly: Temperature {temp_c:.1f} °C deviates "
                f"{temp_dev:+.1f} °C from learned room normal ({base_temp_mean:.1f} °C). "
                f"Flame and smoke sensors remain clear."
            )

            should_alert = True
            if self.last_anomaly_time:
                elapsed = (now_utc - self.last_anomaly_time).total_seconds()
                if elapsed < self.anomaly_cooldown:
                    should_alert = False

            if should_alert:
                self.last_anomaly_time = now_utc

            return {
                "state": RiskState.BASELINE_ANOMALY,
                "event_type": RiskState.BASELINE_ANOMALY,
                "severity": "INFO",
                "should_alert": should_alert,
                "reason": reason_str,
                "metrics": metrics,
            }

        # -------------------------------------------------------------
        # Normal State & All-Clear Transition
        # -------------------------------------------------------------
        self.consecutive_normal_readings += 1

        # Trigger All-Clear event after consecutive normal readings following an active hazard
        if self.hazard_active and self.consecutive_normal_readings >= self.all_clear_consecutive_needed:
            self.hazard_active = False
            self.previous_state = self.last_hazard_state or self.current_state
            self.current_state = RiskState.NORMAL
            return {
                "state": RiskState.NORMAL,
                "event_type": "ALL_CLEAR",
                "severity": "INFO",
                "should_alert": True,
                "reason": f"All clear: Hazard cleared, {self.all_clear_consecutive_needed} consecutive normal readings verified.",
                "metrics": metrics,
            }

        self.previous_state = self.current_state
        self.current_state = RiskState.NORMAL

        return {
            "state": RiskState.NORMAL,
            "event_type": RiskState.NORMAL,
            "severity": "NORMAL",
            "should_alert": False,
            "reason": "All parameters normal within learned room baseline bands.",
            "metrics": metrics,
        }

    def _record_temp_history(self, timestamp: datetime, temp_c: float) -> None:
        """Keep sliding buffer of last 5 minutes of temperature readings."""
        self._temp_history.append((timestamp, temp_c))
        # Remove readings older than 360 seconds (6 minutes)
        cutoff = timestamp - datetime.resolution * 0  # placeholder
        if len(self._temp_history) > 20:
            self._temp_history = self._temp_history[-20:]

    def _calculate_temp_rise_rate(self) -> Optional[float]:
        """Compute rate of change (°C / minute) over recent valid readings."""
        if len(self._temp_history) < 2:
            return 0.0

        t_first, temp_first = self._temp_history[0]
        t_last, temp_last = self._temp_history[-1]

        delta_seconds = (t_last - t_first).total_seconds()
        if delta_seconds < 10.0:
            return 0.0

        delta_temp = temp_last - temp_first
        # Convert °C / second to °C / minute
        rate_c_min = (delta_temp / delta_seconds) * 60.0
        return round(rate_c_min, 2)

    def _parse_iso_time(self, ts_str: Any) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        except Exception:
            return None

    def _empty_metrics(self, reading: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "entry_id": reading.get("entry_id") if reading else None,
            "temperature_c": None,
            "humidity_pct": None,
            "flame_raw": None,
            "smoke_status": None,
            "fire_status": None,
            "servo_angle": None,
            "baseline_temp_mean": None,
            "baseline_hum_mean": None,
            "temp_deviation": None,
            "temp_rate_c_min": None,
            "is_temp_anomalous": False,
        }
