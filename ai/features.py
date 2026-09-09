import pandas as pd
import numpy as np

def extract_features(df, window_size=5):
    """
    Extracts rolling features from the raw flame signal.
    """
    df_features = df.copy()
    
    # Basic rolling statistics
    df_features['rolling_mean'] = df_features['flame_raw'].rolling(window=window_size, min_periods=1).mean()
    df_features['rolling_median'] = df_features['flame_raw'].rolling(window=window_size, min_periods=1).median()
    df_features['rolling_std'] = df_features['flame_raw'].rolling(window=window_size, min_periods=1).std().fillna(0)
    df_features['rolling_min'] = df_features['flame_raw'].rolling(window=window_size, min_periods=1).min()
    df_features['rolling_max'] = df_features['flame_raw'].rolling(window=window_size, min_periods=1).max()
    df_features['signal_range'] = df_features['rolling_max'] - df_features['rolling_min']
    df_features['signal_variance'] = df_features['rolling_std'] ** 2
    
    # Rate of change
    df_features['first_derivative'] = df_features['flame_raw'].diff().fillna(0)
    df_features['absolute_change'] = df_features['first_derivative'].abs()
    
    # Signal stability
    df_features['signal_stability'] = 1.0 / (df_features['rolling_std'] + 1e-5)
    
    return df_features
