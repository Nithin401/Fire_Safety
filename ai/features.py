"""
FireShield AI — Multi-Sensor Feature Engineering & Sensor Fusion Engine

Computes:
- Per-channel rolling statistics (mean, median, std, min, max, variance)
- 1st derivative (Rate of Change / velocity)
- 2nd derivative (Acceleration of thermal/gas rise)
- Cross-channel sensor fusion consistency checks (flame-temp correlation, gas-smoke index)
"""

import pandas as pd
import numpy as np

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes column names between camelCase and snake_case representations.
    """
    renames = {
        'flame_raw': 'flameRaw',
        'temp_c': 'tempC',
        'gas_raw': 'gasRaw',
        'smoke_raw': 'smokeRaw',
        'fire_angle': 'fireAngle'
    }
    return df.rename(columns=renames)

def extract_features(df: pd.DataFrame, window_size: int = 5) -> pd.DataFrame:
    """
    Extracts multi-channel rolling features, derivatives, and cross-channel fusion indicators.
    """
    df_feat = standardize_columns(df.copy())
    
    # Ensure flameRaw exists
    if 'flameRaw' not in df_feat.columns:
        df_feat['flameRaw'] = 900
        
    # Standardize back for legacy callers that inspect df['flame_raw']
    df_feat['flame_raw'] = df_feat['flameRaw']
    
    # 1. Flame Channel Features
    df_feat['rolling_mean'] = df_feat['flameRaw'].rolling(window=window_size, min_periods=1).mean()
    df_feat['rolling_median'] = df_feat['flameRaw'].rolling(window=window_size, min_periods=1).median()
    df_feat['rolling_std'] = df_feat['flameRaw'].rolling(window=window_size, min_periods=1).std().fillna(0)
    df_feat['rolling_min'] = df_feat['flameRaw'].rolling(window=window_size, min_periods=1).min()
    df_feat['rolling_max'] = df_feat['flameRaw'].rolling(window=window_size, min_periods=1).max()
    df_feat['signal_range'] = df_feat['rolling_max'] - df_feat['rolling_min']
    df_feat['signal_variance'] = df_feat['rolling_std'] ** 2
    
    # Flame derivatives (flame drop = negative velocity)
    df_feat['first_derivative'] = df_feat['flameRaw'].diff().fillna(0)
    df_feat['second_derivative'] = df_feat['first_derivative'].diff().fillna(0)
    df_feat['absolute_change'] = df_feat['first_derivative'].abs()
    df_feat['signal_stability'] = 1.0 / (df_feat['rolling_std'] + 1e-5)
    
    # 2. Temperature Channel Features (if present)
    if 'tempC' in df_feat.columns:
        df_feat['temp_rolling_mean'] = df_feat['tempC'].rolling(window=window_size, min_periods=1).mean()
        df_feat['temp_roc'] = df_feat['tempC'].diff().fillna(0)
        df_feat['temp_accel'] = df_feat['temp_roc'].diff().fillna(0)
    else:
        df_feat['tempC'] = 25.0
        df_feat['temp_rolling_mean'] = 25.0
        df_feat['temp_roc'] = 0.0
        df_feat['temp_accel'] = 0.0
        
    # 3. Gas & Smoke Channel Features (if present)
    if 'gasRaw' in df_feat.columns:
        df_feat['gas_rolling_mean'] = df_feat['gasRaw'].rolling(window=window_size, min_periods=1).mean()
        df_feat['gas_roc'] = df_feat['gasRaw'].diff().fillna(0)
    else:
        df_feat['gasRaw'] = 120
        df_feat['gas_rolling_mean'] = 120.0
        df_feat['gas_roc'] = 0.0
        
    if 'smokeRaw' in df_feat.columns:
        df_feat['smoke_rolling_mean'] = df_feat['smokeRaw'].rolling(window=window_size, min_periods=1).mean()
        df_feat['smoke_roc'] = df_feat['smokeRaw'].diff().fillna(0)
    else:
        df_feat['smokeRaw'] = 120
        df_feat['smoke_rolling_mean'] = 120.0
        df_feat['smoke_roc'] = 0.0
        
    # 4. Multi-Sensor Fusion Consistency & Confidence Indicators
    # A true fire exhibits: Flame ADC drops (<500) AND Temp rises (>1.0C roc or >35C) AND Gas rises (>250)
    # A false alarm exhibits: Flame ADC drops (<500) BUT Temp is flat (roc <0.5C) AND Gas is flat (<200)
    
    # Normalized flame drop indicator (0.0 to 1.0)
    flame_drop_norm = np.clip((850.0 - df_feat['rolling_mean']) / 600.0, 0.0, 1.0)
    
    # Normalized temperature rise indicator (0.0 to 1.0)
    temp_rise_norm = np.clip((df_feat['temp_rolling_mean'] - 26.0) / 25.0, 0.0, 1.0)
    
    # Normalized gas surge indicator (0.0 to 1.0)
    gas_surge_norm = np.clip((df_feat['gas_rolling_mean'] - 150.0) / 350.0, 0.0, 1.0)
    
    # Cross-sensor consistency product
    df_feat['flame_temp_correlation'] = flame_drop_norm * temp_rise_norm
    df_feat['gas_smoke_index'] = (gas_surge_norm + np.clip((df_feat['smoke_rolling_mean'] - 150.0) / 350.0, 0.0, 1.0)) / 2.0
    
    # Fused confidence score: High only when flame + thermal/gas co-occur
    # Weight: 50% flame drop, 30% temperature rise, 20% gas surge
    df_feat['fusion_confidence_score'] = (0.50 * flame_drop_norm) + (0.30 * temp_rise_norm) + (0.20 * gas_surge_norm)
    
    # False alarm suspicion flag: flame drops sharply without temperature or gas support
    df_feat['false_alarm_suspect'] = (flame_drop_norm > 0.6) & (temp_rise_norm < 0.15) & (gas_surge_norm < 0.15)
    
    return df_feat
