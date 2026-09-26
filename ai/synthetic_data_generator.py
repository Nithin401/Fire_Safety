"""
FireShield AI — Physically-Plausible Multi-Sensor Synthetic Data Generator

Generates realistic time-series sensor sessions for NORMAL, FIRE, and FALSE_ALARM conditions.
Supports:
- flameRaw (ADC 0-1023)
- tempC (Celsius)
- humidity (% RH)
- gasRaw (ADC 0-1023)
- smokeRaw (ADC 0-1023)
- fireAngle (0-180 deg)
- metadata and labels compliant with docs/dataset_schema.md

Output sessions are saved to data/synthetic/ and tagged data_source='synthetic'.
"""

import os
import argparse
import datetime
import numpy as np
import pandas as pd

def generate_session(session_id: str, 
                     condition: str, 
                     device_id: str = "dev_001", 
                     room_id: str = "Kitchen",
                     num_samples: int = 120, 
                     sample_interval_sec: float = 1.0,
                     fire_angle: int = 90,
                     seed: int = None) -> pd.DataFrame:
    """
    Generates a single synthetic session dataframe.
    """
    if seed is not None:
        np.random.seed(seed)
        
    start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=num_samples * sample_interval_sec)
    timestamps = [
        (start_time + datetime.timedelta(seconds=i * sample_interval_sec)).isoformat()
        for i in range(num_samples)
    ]
    
    # 1. Base ambient levels
    base_flame = np.random.uniform(880, 930)
    base_temp = np.random.uniform(23.5, 26.5)
    base_hum = np.random.uniform(50.0, 60.0)
    base_gas = np.random.uniform(110, 150)
    base_smoke = np.random.uniform(90, 130)
    
    # Noise terms
    flame_noise = np.random.normal(0, 4.0, num_samples)
    temp_noise = np.random.normal(0, 0.15, num_samples)
    hum_noise = np.random.normal(0, 0.25, num_samples)
    gas_noise = np.random.normal(0, 3.0, num_samples)
    smoke_noise = np.random.normal(0, 2.5, num_samples)
    
    flame_vals = base_flame + flame_noise
    temp_vals = base_temp + temp_noise
    hum_vals = base_hum + hum_noise
    gas_vals = base_gas + gas_noise
    smoke_vals = base_smoke + smoke_noise
    angle_vals = np.full(num_samples, 90, dtype=int)
    
    labels = np.full(num_samples, "NORMAL", dtype=object)
    
    if condition == "FIRE":
        # Warmup for ~20% of session, then thermal/flame exponential ramp
        warmup = int(num_samples * 0.2)
        ramp_len = int(num_samples * 0.4)
        peak_len = num_samples - warmup - ramp_len
        
        # Sigmoidal / exponential escalation
        t_ramp = np.linspace(0, 1, ramp_len)
        ramp_curve = 1.0 / (1.0 + np.exp(-10 * (t_ramp - 0.4)))
        
        # Flame drops sharply from ~900 down to ~150-250 (IR sensor saturation)
        flame_drop = np.random.uniform(650, 750)
        flame_vals[warmup:warmup + ramp_len] -= ramp_curve * flame_drop
        flame_vals[warmup + ramp_len:] -= flame_drop
        
        # Temperature rises by 35-50°C
        temp_rise = np.random.uniform(35.0, 55.0)
        temp_vals[warmup:warmup + ramp_len] += ramp_curve * temp_rise
        temp_vals[warmup + ramp_len:] += temp_rise
        
        # Humidity drops during intense combustion
        hum_vals[warmup:] -= 12.0
        
        # Gas and smoke surge
        gas_surge = np.random.uniform(400, 600)
        smoke_surge = np.random.uniform(450, 650)
        gas_vals[warmup:warmup + ramp_len] += ramp_curve * gas_surge
        gas_vals[warmup + ramp_len:] += gas_surge
        smoke_vals[warmup:warmup + ramp_len] += ramp_curve * smoke_surge
        smoke_vals[warmup + ramp_len:] += smoke_surge
        
        # Fire ground-truth angle
        angle_vals[warmup:] = fire_angle
        labels[warmup:] = "FIRE"
        
    elif condition == "FALSE_ALARM":
        # Short transient optical/thermal spike on ONLY one channel (e.g. camera flash, lighter glance)
        # Without correlated gas or prolonged temperature rise
        spike_start = int(num_samples * 0.4)
        spike_duration = np.random.randint(4, 8)
        
        # Sudden drop in flame raw ADC that recovers in 4-6 seconds
        flame_vals[spike_start:spike_start + spike_duration] -= np.random.uniform(450, 600)
        
        # Gas and temperature do NOT correlate
        labels[spike_start:spike_start + spike_duration] = "FALSE_ALARM"
        angle_vals[spike_start:spike_start + spike_duration] = fire_angle

    # Bounds clipping
    flame_vals = np.clip(flame_vals, 0, 1023).astype(int)
    gas_vals = np.clip(gas_vals, 0, 1023).astype(int)
    smoke_vals = np.clip(smoke_vals, 0, 1023).astype(int)
    hum_vals = np.clip(hum_vals, 0.0, 100.0).round(2)
    temp_vals = np.clip(temp_vals, -20.0, 120.0).round(2)
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "sessionId": session_id,
        "deviceId": device_id,
        "roomId": room_id,
        "flameRaw": flame_vals,
        "tempC": temp_vals,
        "humidity": hum_vals,
        "gasRaw": gas_vals,
        "smokeRaw": smoke_vals,
        "fireAngle": angle_vals,
        "label": labels,
        "distance_cm": 100 if condition != "NORMAL" else 0,
        "environment_notes": f"Synthetic simulation of {condition} condition",
        "data_source": "synthetic"
    })
    
    return df

def generate_full_dataset(output_dir: str = "data/synthetic", 
                          n_normal: int = 15, 
                          n_fire: int = 15, 
                          n_false: int = 10,
                          samples_per_session: int = 120,
                          base_seed: int = 42):
    """
    Generates a full corpus of synthetic sessions across NORMAL, FIRE, and FALSE_ALARM.
    """
    os.makedirs(output_dir, exist_ok=True)
    all_files = []
    
    # 1. Normal Sessions
    for i in range(1, n_normal + 1):
        s_id = f"SYNTH_NORM_{i:03d}"
        df = generate_session(s_id, "NORMAL", num_samples=samples_per_session, seed=base_seed + i)
        path = os.path.join(output_dir, f"{s_id}.csv")
        df.to_csv(path, index=False)
        all_files.append(path)
        
    # 2. Fire Sessions with varied angles and intensities
    for i in range(1, n_fire + 1):
        s_id = f"SYNTH_FIRE_{i:03d}"
        angle = int(np.random.choice([30, 45, 60, 90, 120, 135, 150]))
        df = generate_session(s_id, "FIRE", num_samples=samples_per_session, fire_angle=angle, seed=base_seed + 100 + i)
        path = os.path.join(output_dir, f"{s_id}.csv")
        df.to_csv(path, index=False)
        all_files.append(path)
        
    # 3. False Alarm Sessions
    for i in range(1, n_false + 1):
        s_id = f"SYNTH_FALSE_{i:03d}"
        angle = int(np.random.choice([45, 90, 135]))
        df = generate_session(s_id, "FALSE_ALARM", num_samples=samples_per_session, fire_angle=angle, seed=base_seed + 200 + i)
        path = os.path.join(output_dir, f"{s_id}.csv")
        df.to_csv(path, index=False)
        all_files.append(path)
        
    print(f"[SUCCESS] Generated {len(all_files)} synthetic sessions in {output_dir}")
    return all_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Multi-Sensor Data Generator")
    parser.add_argument("--output-dir", type=str, default="data/synthetic")
    parser.add_argument("--n-normal", type=int, default=15)
    parser.add_argument("--n-fire", type=int, default=15)
    parser.add_argument("--n-false", type=int, default=10)
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    generate_full_dataset(
        output_dir=args.output_dir,
        n_normal=args.n_normal,
        n_fire=args.n_fire,
        n_false=args.n_false,
        samples_per_session=args.samples,
        base_seed=args.seed
    )
