"""
FireShield AI — Hybrid Risk Engine (Rule-Based Backstop + ML Inference)

Combines:
1. Deterministic Rule-Based Engine (Hard Safety Backstop)
2. Machine Learning Classifier (ONNX / Scikit-Learn Model for False Alarm Suppression)

Rule: ML is advisory. It can suppress false alarms and boost confidence,
but the deterministic safety backstop ALWAYS has override authority on FIRE.
"""

import os
import joblib
import numpy as np
import pandas as pd
from ai.risk_engine import RiskEngine

class HybridRiskEngine:
    def __init__(self, model_path: str = "ml/models/v1/model.pkl", use_ml: bool = True):
        self.rule_engine = RiskEngine()
        self.use_ml = use_ml
        self.model_bundle = None
        
        if self.use_ml and os.path.exists(model_path):
            try:
                self.model_bundle = joblib.load(model_path)
                print(f"[INFO] HybridRiskEngine loaded ML model from {model_path}")
            except Exception as e:
                print(f"[WARNING] Failed to load ML model ({e}). Operating in rule-only mode.")
                self.use_ml = False
        else:
            self.use_ml = False

    def evaluate_hybrid_risk(self, feature_row: dict) -> tuple[float, str, dict]:
        """
        Evaluates risk score (0-100) and fire state ('SAFE', 'WARNING', 'HIGH_RISK', 'FIRE').
        Returns (risk_score, fire_state, metadata).
        """
        # 1. Deterministic Rule Evaluation (Safety Backstop)
        dev = feature_row.get('deviation_from_baseline', 0)
        roc = feature_row.get('first_derivative', 0)
        anom = feature_row.get('anomaly_flag_zscore', 0)
        rule_score, rule_state = self.rule_engine.evaluate_risk(dev, roc, anom)
        
        metadata = {
            'rule_score': rule_score,
            'rule_state': rule_state,
            'ml_active': False,
            'ml_prediction': None,
            'ml_probabilities': None
        }
        
        # If ML is not available, return rule engine decision directly
        if not self.use_ml or self.model_bundle is None:
            return rule_score, rule_state, metadata
            
        # 2. ML Model Inference
        try:
            feature_cols = self.model_bundle['feature_cols']
            clf = self.model_bundle['model']
            inv_map = self.model_bundle['inv_label_map']
            
            # Construct input dataframe with column names to avoid warnings
            x_df = pd.DataFrame([{col: feature_row.get(col, 0.0) for col in feature_cols}], dtype=np.float32)
            
            pred_class_idx = clf.predict(x_df)[0]
            pred_probs = clf.predict_proba(x_df)[0]
            pred_label = inv_map[pred_class_idx]
            
            metadata['ml_active'] = True
            metadata['ml_prediction'] = pred_label
            metadata['ml_probabilities'] = {inv_map[i]: float(p) for i, p in enumerate(pred_probs)}
            
            fire_prob = metadata['ml_probabilities'].get('FIRE', 0.0)
            false_prob = metadata['ml_probabilities'].get('FALSE_ALARM', 0.0)
            
            # Hybrid Blending Logic:
            # - If ML predicts FALSE_ALARM with high probability (>0.6) and persistence is not yet confirmed,
            #   downgrade to WARNING to suppress false suppression
            # - Hard safety backstop: If rule engine confirmed persistent fire (persistent_high_count >= threshold),
            #   or rule_state is FIRE without FALSE_ALARM consensus, deterministic backstop triggers FIRE!
            is_persistent_fire = (self.rule_engine.persistent_high_count >= self.rule_engine.persistence_threshold)
            
            if pred_label == "FALSE_ALARM" and false_prob > 0.6 and not is_persistent_fire:
                final_score = min(rule_score, 45.0)
                final_state = "WARNING"
            elif is_persistent_fire or (rule_state == "FIRE" and pred_label != "FALSE_ALARM"):
                final_score = max(rule_score, 90.0)
                final_state = "FIRE"
            elif pred_label == "FIRE" and fire_prob > 0.6:
                final_score = max(rule_score, 85.0 + (fire_prob * 15.0))
                final_state = "FIRE"
            else:
                final_score = rule_score
                final_state = rule_state
                
            return float(final_score), final_state, metadata
            
        except Exception as e:
            # Safe fallback on ML error
            print(f"[ERROR] ML inference error: {e}. Falling back to rule engine.")
            return rule_score, rule_state, metadata
