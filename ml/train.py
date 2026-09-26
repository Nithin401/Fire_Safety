"""
FireShield AI — Multi-Model Training & Benchmark Pipeline

Trains candidate models on session-separated feature data:
1. Rule-Based Baseline Engine (benchmark)
2. Random Forest Classifier
3. Histogram Gradient Boosted Trees (fast, robust gradient boosting)

Exports best performing model to joblib and ONNX formats.
"""

import os
import argparse
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

FEATURE_COLS = [
    'rolling_mean', 'signal_variance', 'first_derivative', 'second_derivative',
    'deviation_from_baseline',
    'temp_rolling_mean', 'temp_roc', 'temp_accel', 'temp_deviation',
    'gas_rolling_mean', 'gas_roc', 'gas_deviation',
    'smoke_rolling_mean', 'smoke_roc',
    'flame_temp_correlation', 'gas_smoke_index', 'fusion_confidence_score',
    'z_score', 'time_since_last_anomaly'
]

LABEL_MAP = {'NORMAL': 0, 'FIRE': 1, 'FALSE_ALARM': 2}
INV_LABEL_MAP = {0: 'NORMAL', 1: 'FIRE', 2: 'FALSE_ALARM'}

def load_data(splits_dir: str):
    train_df = pd.read_parquet(os.path.join(splits_dir, "train.parquet"))
    val_df = pd.read_parquet(os.path.join(splits_dir, "val.parquet"))
    test_df = pd.read_parquet(os.path.join(splits_dir, "test.parquet"))
    
    # Fill any NaNs
    X_train = train_df[FEATURE_COLS].fillna(0).astype(np.float32)
    y_train = train_df['label'].map(LABEL_MAP).values
    
    X_val = val_df[FEATURE_COLS].fillna(0).astype(np.float32)
    y_val = val_df['label'].map(LABEL_MAP).values
    
    X_test = test_df[FEATURE_COLS].fillna(0).astype(np.float32)
    y_test = test_df['label'].map(LABEL_MAP).values
    
    return (X_train, y_train), (X_val, y_val), (X_test, y_test), (train_df, val_df, test_df)

def train_and_export_models(splits_dir: str = "data/features/v1/splits", 
                           output_dir: str = "ml/models/v1"):
    os.makedirs(output_dir, exist_ok=True)
    (X_train, y_train), (X_val, y_val), (X_test, y_test), (train_df, val_df, test_df) = load_data(splits_dir)
    
    models = {
        'random_forest': RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, class_weight='balanced'),
        'gradient_boosting': HistGradientBoostingClassifier(max_iter=100, random_state=42)
    }
    
    results = {}
    best_model_name = None
    best_val_f1 = -1.0
    best_model = None
    
    print("\n--- Training Candidate ML Models ---")
    for name, clf in models.items():
        print(f"\n[TRAIN] Training {name}...")
        clf.fit(X_train, y_train)
        
        val_preds = clf.predict(X_val)
        val_f1 = f1_score(y_val, val_preds, average='macro')
        results[name] = {
            'model': clf,
            'val_f1': val_f1,
            'val_report': classification_report(y_val, val_preds, target_names=['NORMAL', 'FIRE', 'FALSE_ALARM'], output_dict=True)
        }
        print(f"  -> Validation Macro F1: {val_f1:.4f}")
        
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_model_name = name
            best_model = clf
            
    print(f"\n[SELECTION] Best Model: {best_model_name} (Val F1: {best_val_f1:.4f})")
    
    # Save best model to joblib PKL
    pkl_path = os.path.join(output_dir, "model.pkl")
    joblib.dump({
        'model': best_model,
        'model_name': best_model_name,
        'feature_cols': FEATURE_COLS,
        'label_map': LABEL_MAP,
        'inv_label_map': INV_LABEL_MAP
    }, pkl_path)
    print(f"[SUCCESS] Saved model to {pkl_path}")
    
    # Export to ONNX for lightweight cross-platform / edge inference
    try:
        initial_type = [('float_input', FloatTensorType([None, len(FEATURE_COLS)]))]
        onnx_model = convert_sklearn(best_model, initial_types=initial_type, target_opset=12)
        onnx_path = os.path.join(output_dir, "model.onnx")
        with open(onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"[SUCCESS] Exported ONNX model to {onnx_path}")
    except Exception as e:
        print(f"[WARNING] ONNX conversion error: {e}")
        
    return best_model_name, results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FireShield Models")
    parser.add_argument("--splits-dir", default="data/features/v1/splits")
    parser.add_argument("--output-dir", default="ml/models/v1")
    args = parser.parse_args()
    
    train_and_export_models(args.splits_dir, args.output_dir)
