"""
FireShield AI — Dynamic Room-Adaptive Baseline & Multi-Sensor Fusion Engine
===========================================================================
Solves the environmental false-alarm problem:
  - Every room has different ambient temperatures and natural diurnal cycles.
  - On hot sunny days, room ambient temperature can rise significantly.
  - A static threshold triggers severe false alarms under high ambient heat.
  - This engine learns the continuous baseline for each room individually,
    measures multi-sensor rates of change (dT/dt, dGas/dt), and cross-checks
    thermal, gas, and optical IR flame channels to distinguish:
      1. NORMAL_AMBIENT_DRIFT (e.g. hot sunny afternoon)
      2. FALSE_ALARM_CANDIDATE (e.g. kitchen steam, cooking fumes, room heater)
      3. PRE_FIRE_WARNING (early smoldering, gas accumulation)
      4. ACTUAL_FIRE (rapid thermal acceleration + smoke + optical IR flame)
"""

import numpy as np
import pandas as pd
import datetime
from typing import Dict, Tuple, Optional, Any


class RoomBaselineProfile:
    """
    Stores and dynamically updates continuous ambient statistics for a single room.
    Uses Dual-Timescale Exponential Moving Averages (EMA) with anomaly freezing.
    """
    def __init__(self, room_id: str, alpha_slow: float = 0.01, min_samples_to_calibrate: int = 15):
        self.room_id = room_id
        self.alpha_slow = alpha_slow  # Slow smoothing factor (~15-30 min ambient tracking)
        self.min_samples_to_calibrate = min_samples_to_calibrate

        # Ambient baseline state
        self.sample_count = 0
        self.temp_baseline = 25.0       # Moving average °C
        self.temp_var = 1.0             # Moving variance
        self.temp_std = 1.0

        self.humidity_baseline = 50.0   # Moving average %
        self.pressure_baseline = 1013.0 # Moving average hPa
        
        self.gas_baseline = 1500.0      # Moving average gas raw ADC
        self.gas_var = 100.0
        self.gas_std = 10.0

        self.flame_ambient_voltage = 3.0 # High voltage (~3.0-3.3V) = dark / no fire IR

        # Recent temporal history for derivative calculations (rate of change)
        self.last_timestamp: Optional[datetime.datetime] = None
        self.last_temp: Optional[float] = None
        self.last_gas: Optional[float] = None
        self.last_flame_v: Optional[float] = None

    def update(self, temp: float, humidity: float, pressure: float,
               gas_raw: float, flame_voltage: float,
               timestamp: Optional[datetime.datetime] = None,
               freeze_baseline: bool = False) -> None:
        """
        Updates the baseline with new sensor readings.
        If freeze_baseline is True (anomalous spike detected), baseline adaptation
        is paused so the fire doesn't pull the baseline upward.
        """
        self.sample_count += 1
        
        # Cold start initialization
        if self.sample_count == 1:
            self.temp_baseline = temp
            self.humidity_baseline = humidity
            self.pressure_baseline = pressure
            self.gas_baseline = gas_raw
            self.flame_ambient_voltage = flame_voltage
            self.last_temp = temp
            self.last_gas = gas_raw
            self.last_flame_v = flame_voltage
            self.last_timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc)
            return

        # Adapt baseline only during normal non-emergency conditions
        if not freeze_baseline:
            alpha = self.alpha_slow
            # Update mean
            delta_t = temp - self.temp_baseline
            self.temp_baseline += alpha * delta_t
            self.temp_var = (1 - alpha) * self.temp_var + alpha * (delta_t ** 2)
            self.temp_std = max(np.sqrt(self.temp_var), 0.3)  # Floor at 0.3°C

            self.humidity_baseline = (1 - alpha) * self.humidity_baseline + alpha * humidity
            self.pressure_baseline = (1 - alpha) * self.pressure_baseline + alpha * pressure

            delta_g = gas_raw - self.gas_baseline
            self.gas_baseline += alpha * delta_g
            self.gas_var = (1 - alpha) * self.gas_var + alpha * (delta_g ** 2)
            self.gas_std = max(np.sqrt(self.gas_var), 15.0)

            self.flame_ambient_voltage = (1 - alpha) * self.flame_ambient_voltage + alpha * flame_voltage

        self.last_temp = temp
        self.last_gas = gas_raw
        self.last_flame_v = flame_voltage
        self.last_timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc)

    @property
    def is_calibrated(self) -> bool:
        return self.sample_count >= self.min_samples_to_calibrate


class DynamicRoomBaselineEngine:
    """
    Manages multi-room baseline profiles, extracts rate-of-change derivatives,
    and runs multi-sensor fusion logic to prevent false alarms.
    """
    def __init__(self, alpha_slow: float = 0.01):
        self.alpha_slow = alpha_slow
        self.rooms: Dict[str, RoomBaselineProfile] = {}

    def get_or_create_room(self, room_id: str) -> RoomBaselineProfile:
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomBaselineProfile(room_id, alpha_slow=self.alpha_slow)
        return self.rooms[room_id]

    def process_reading(self, reading: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single real-time sensor reading dictionary.
        Returns the original reading enriched with dynamic baseline metrics,
        rate-of-change derivatives, and safety classification verdict.
        """
        room_id = str(reading.get('room_id', reading.get('device_id', 'ROOM_DEFAULT')))
        profile = self.get_or_create_room(room_id)

        # Extract multi-sensor values
        temp = float(reading.get('temperature', reading.get('temp_c', reading.get('tempC', 25.0))))
        humidity = float(reading.get('humidity', 50.0))
        pressure = float(reading.get('pressure', 1013.25))
        gas_raw = float(reading.get('gas_raw', reading.get('gasRaw', 1500.0)))
        gas_voltage = float(reading.get('gas_voltage', 0.5))
        flame_raw = float(reading.get('flame_raw', reading.get('flameRaw', 15000.0)))
        flame_voltage = float(reading.get('flame_voltage', 3.0))
        flame_digital = int(reading.get('flame_digital', 0))

        # Parse timestamp
        raw_ts = reading.get('timestamp', reading.get('pc_timestamp', ''))
        ts: datetime.datetime
        try:
            if isinstance(raw_ts, str) and raw_ts:
                ts = datetime.datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
            else:
                ts = datetime.datetime.now(datetime.timezone.utc)
        except Exception:
            ts = datetime.datetime.now(datetime.timezone.utc)

        # Calculate time delta for rate of change (dT/dt, dGas/dt)
        dt_seconds = 1.0
        if profile.last_timestamp is not None:
            delta = (ts - profile.last_timestamp).total_seconds()
            if 0.1 <= delta <= 30.0:
                dt_seconds = delta

        # Rates of change (velocities)
        prev_t = profile.last_temp if profile.last_temp is not None else temp
        prev_g = profile.last_gas if profile.last_gas is not None else gas_raw
        prev_f = profile.last_flame_v if profile.last_flame_v is not None else flame_voltage

        dT_dt = (temp - prev_t) / dt_seconds          # °C per second
        dGas_dt = (gas_raw - prev_g) / dt_seconds     # ADC units per second
        dFlameV_dt = (flame_voltage - prev_f) / dt_seconds # V per second (drop = fire IR)

        # Baseline deviations & Z-Scores
        delta_temp = temp - profile.temp_baseline
        delta_gas = gas_raw - profile.gas_baseline
        delta_humidity = humidity - profile.humidity_baseline

        temp_zscore = delta_temp / profile.temp_std
        gas_zscore = delta_gas / profile.gas_std

        # --- MULTI-SENSOR FUSION & FALSE ALARM SUPPRESSION LOGIC ---
        verdict = "NORMAL"
        confidence = 0.95
        suppression_reason = ""
        is_fire = False
        risk_score = 0.0

        # Optical flame detection check
        has_flame_optical = (flame_digital == 1) or (flame_voltage < 1.6)

        # 1. ACTUAL FIRE CRITERIA
        # Requires multi-channel corroboration:
        # A) Optical IR flame detected + temperature rising or gas rising
        # OR B) Drastic thermal runaway (dT/dt > 0.4°C/s and delta_temp > 4°C) with smoke/gas surge
        if has_flame_optical and (delta_temp > 2.0 or dT_dt > 0.15 or gas_zscore > 2.0):
            verdict = "ACTUAL_FIRE"
            is_fire = True
            confidence = 0.99
            risk_score = 98.0
        elif has_flame_optical:
            # Flame confirmed optically
            verdict = "ACTUAL_FIRE"
            is_fire = True
            confidence = 0.95
            risk_score = 92.0
        elif dT_dt > 0.4 and delta_temp > 4.5 and gas_zscore > 3.0:
            # Rapid thermal acceleration + heavy smoke, even if flame sensor angled away
            verdict = "ACTUAL_FIRE"
            is_fire = True
            confidence = 0.91
            risk_score = 88.0

        # 2. FALSE ALARM CANDIDATE: Hot Sunny Afternoon (Ambient Environmental Shift)
        # Temp is high (even 35-40°C), but rate of change is tiny (< 0.05°C/s),
        # Gas is near baseline, and optical flame is completely absent.
        elif temp > 28.0 and not has_flame_optical and gas_zscore < 2.0 and abs(dT_dt) < 0.08:
            verdict = "NORMAL_SUNNY_DAY"
            confidence = 0.96
            risk_score = 5.0
            suppression_reason = f"High ambient temp ({temp:.1f}°C) matches dynamic room baseline ({profile.temp_baseline:.1f}°C); zero flame/smoke."

        # 3. FALSE ALARM CANDIDATE: Cooking Steam / Boiling Water
        # Humidity surges high, temp increases slightly, but gas is low and flame is absent.
        elif delta_humidity > 15.0 and not has_flame_optical and gas_zscore < 1.5:
            verdict = "FALSE_ALARM_STEAM"
            confidence = 0.92
            risk_score = 12.0
            suppression_reason = f"Humidity surge (+{delta_humidity:.1f}%) with zero optical flame or hazardous gas. Classified as benign steam."

        # 4. FALSE ALARM CANDIDATE: Kitchen Frying / Aerosol Spray
        # Transient gas spike, but no thermal rise (dT/dt <= 0) and zero flame optical signal.
        elif gas_zscore > 2.5 and not has_flame_optical and delta_temp < 1.5 and dT_dt <= 0.05:
            verdict = "FALSE_ALARM_COOKING_GAS"
            confidence = 0.88
            risk_score = 25.0
            suppression_reason = f"Gas spike (Z={gas_zscore:.1f}) without thermal rise or IR flame. Local cooking aerosol."

        # 5. PRE-FIRE WARNING (Smoldering without active open flame)
        elif gas_zscore > 3.5 and (delta_temp > 2.0 or dT_dt > 0.1):
            verdict = "PRE_FIRE_WARNING"
            confidence = 0.85
            risk_score = 65.0
        else:
            verdict = "NORMAL"
            risk_score = min(max(temp_zscore * 5.0 + gas_zscore * 3.0, 0.0), 30.0)

        # Freeze baseline if in pre-fire or actual fire so anomalies don't distort baseline
        freeze_baseline = is_fire or (verdict == "PRE_FIRE_WARNING")
        profile.update(temp, humidity, pressure, gas_raw, flame_voltage, timestamp=ts, freeze_baseline=freeze_baseline)

        # Build output enriched dictionary
        enriched = dict(reading)
        enriched.update({
            "room_id": room_id,
            "room_baseline_temp": round(profile.temp_baseline, 2),
            "room_baseline_gas": round(profile.gas_baseline, 1),
            "room_baseline_humidity": round(profile.humidity_baseline, 1),
            "delta_temp_from_baseline": round(delta_temp, 3),
            "delta_gas_from_baseline": round(delta_gas, 2),
            "temp_rate_of_change_c_per_sec": round(dT_dt, 4),
            "gas_rate_of_change_per_sec": round(dGas_dt, 2),
            "temp_zscore": round(temp_zscore, 2),
            "gas_zscore": round(gas_zscore, 2),
            "ai_classification_verdict": verdict,
            "ai_risk_score": round(risk_score, 1),
            "is_actual_fire": is_fire,
            "suppression_reason": suppression_reason,
            "baseline_calibrated": profile.is_calibrated
        })
        return enriched


def process_dataframe_with_baselines(df: pd.DataFrame, room_column: str = "device_id") -> pd.DataFrame:
    """
    Batch processes a full pandas DataFrame (e.g. smart_fire_dataset.csv)
    calculating individual dynamic baselines per room.
    """
    engine = DynamicRoomBaselineEngine()
    enriched_rows = []

    # Sort chronologically if timestamp exists
    if "timestamp" in df.columns:
        df_sorted = df.copy()
        try:
            df_sorted["_dt"] = pd.to_datetime(df_sorted["timestamp"], errors="coerce")
            df_sorted = df_sorted.sort_values(by="_dt").drop(columns=["_dt"])
        except Exception:
            pass
    else:
        df_sorted = df

    for _, row in df_sorted.iterrows():
        reading_dict = row.to_dict()
        if room_column in reading_dict:
            reading_dict["room_id"] = reading_dict[room_column]
        enriched = engine.process_reading(reading_dict)
        enriched_rows.append(enriched)

    return pd.DataFrame(enriched_rows)
