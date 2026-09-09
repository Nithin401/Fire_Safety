import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

def calculate_baseline(df, window_size=50):
    """
    Estimates the baseline from NORMAL data using a moving average or median.
    """
    df['baseline'] = df['flame_raw'].rolling(window=window_size, min_periods=1).median()
    df['deviation_from_baseline'] = df['flame_raw'] - df['baseline']
    return df

def detect_anomalies_zscore(df, threshold=3.0):
    """
    Simple rolling z-score anomaly detection.
    """
    df['rolling_mean_long'] = df['flame_raw'].rolling(window=100, min_periods=1).mean()
    df['rolling_std_long'] = df['flame_raw'].rolling(window=100, min_periods=1).std().fillna(1e-5)
    
    df['z_score'] = (df['flame_raw'] - df['rolling_mean_long']) / (df['rolling_std_long'] + 1e-5)
    df['anomaly_flag_zscore'] = (df['z_score'].abs() > threshold).astype(int)
    return df

def detect_anomalies_isolation_forest(df):
    """
    Isolation forest for multi-dimensional anomaly detection when enough data exists.
    """
    if not SKLEARN_AVAILABLE or len(df) < 50:
        df['anomaly_score_if'] = 0
        df['anomaly_flag_if'] = 0
        return df
        
    features = ['flame_raw', 'deviation_from_baseline', 'first_derivative']
    X = df[features].fillna(0)
    
    clf = IsolationForest(contamination=0.05, random_state=42)
    preds = clf.fit_predict(X)
    
    df['anomaly_score_if'] = -clf.score_samples(X)
    df['anomaly_flag_if'] = (preds == -1).astype(int)
    
    return df
