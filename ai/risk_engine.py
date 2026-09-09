import pandas as pd

class RiskEngine:
    def __init__(self, deviation_threshold=50, persistence_threshold=3, anomaly_weight=20):
        self.deviation_threshold = deviation_threshold
        self.persistence_threshold = persistence_threshold
        self.anomaly_weight = anomaly_weight
        self.persistent_high_count = 0

    def evaluate_risk(self, deviation, roc, anomaly_flag):
        """
        Evaluates risk based on deviation, rate of change (roc), and anomaly detection.
        Returns a risk score (0-100) and state (SAFE, WARNING, HIGH_RISK, FIRE).
        """
        risk_score = 0
        
        # 1. Deviation factor (assuming IR flame sensor drops in resistance/voltage when fire is near, 
        # but depending on sensor, it might increase or decrease. Assuming deviation magnitude matters).
        if abs(deviation) > self.deviation_threshold:
            risk_score += min(50, abs(deviation) * 0.5)
            self.persistent_high_count += 1
        else:
            self.persistent_high_count = max(0, self.persistent_high_count - 1)
            
        # 2. Rate of Change (Sudden spikes)
        if abs(roc) > 20:
            risk_score += 15
            
        # 3. Anomaly Flag
        if anomaly_flag > 0:
            risk_score += self.anomaly_weight
            
        # 4. Persistence
        if self.persistent_high_count >= self.persistence_threshold:
            risk_score += 20
            
        # Cap at 100
        risk_score = min(100, max(0, risk_score))
        
        # Determine State
        if risk_score < 30:
            state = "SAFE"
        elif risk_score < 60:
            state = "WARNING"
        elif risk_score < 85:
            state = "HIGH_RISK"
        else:
            state = "FIRE"
            
        return risk_score, state

def run_risk_engine(df):
    """
    Applies the risk engine across the dataset.
    """
    engine = RiskEngine()
    
    risk_scores = []
    states = []
    
    for idx, row in df.iterrows():
        dev = row.get('deviation_from_baseline', 0)
        roc = row.get('first_derivative', 0)
        anomaly = row.get('anomaly_flag_if', row.get('anomaly_flag_zscore', 0))
        
        score, state = engine.evaluate_risk(dev, roc, anomaly)
        risk_scores.append(score)
        states.append(state)
        
    df['risk_score'] = risk_scores
    df['state'] = states
    
    return df
