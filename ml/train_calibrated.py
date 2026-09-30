#!/usr/bin/env python3
"""
FireShield AI — Calibrated Multi-Sensor ML Model Training & Evaluation Pipeline
================================================================================
Trains multi-sensor machine learning models using dynamic room baseline features
to maximize True Positive Fire Detection while reducing False Alarms to ~0%.

Usage:
  python ml/train_calibrated.py --data data/processed/smart_fire_dataset_calibrated.csv --output-dir ml/models/v1
"""

import os
import sys
import json
import argparse
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Core Feature Configuration
CALIBRATED_FEATURE_COLS = [
    # 1. Thermal Channel & Dynamic Room Baseline
    "temperature",
    "room_baseline_temp",
    "delta_temp_from_baseline",
    "temp_rate_of_change_c_per_sec",
    "temp_zscore",
    
    # 2. Gas / Smoke Channel & Dynamic Baseline
    "gas_raw",
    "gas_voltage",
    "room_baseline_gas",
    "delta_gas_from_baseline",
    "gas_rate_of_change_per_sec",
    "gas_zscore",
    
    # 3. Optical Infrared Flame Channel
    "flame_raw",
    "flame_voltage",
    "flame_digital",
    
    # 4. Environmental Context
    "humidity",
    "pressure"
]

# Standard 3-class target mapping for the Hybrid Risk Engine
TARGET_MAP = {
    "NORMAL": 0,
    "NORMAL_SUNNY_DAY": 0,
    "FALSE_ALARM_STEAM": 2,
    "FALSE_ALARM_COOKING_GAS": 2,
    "PRE_FIRE_WARNING": 1,
    "ACTUAL_FIRE": 1,
    "FIRE": 1,
    "FALSE_ALARM": 2
}

INV_TARGET_MAP = {
    0: "NORMAL",
    1: "FIRE",
    2: "FALSE_ALARM"
}


def prepare_dataset(data_path: str):
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset '{data_path}' not found. Run tools/preprocess_and_calibrate.py first.")

    df = pd.read_csv(data_path)

    # Determine ground-truth label column
    label_col = None
    if "ai_classification_verdict" in df.columns:
        label_col = "ai_classification_verdict"
    elif "fire_state" in df.columns:
        label_col = "fire_state"
    elif "label" in df.columns:
        label_col = "label"
    else:
        raise ValueError("Could not find a valid label column in dataset.")

    # Filter features that exist in the dataframe
    active_features = [f for f in CALIBRATED_FEATURE_COLS if f in df.columns]
    print(f"[+] Active Feature Count: {len(active_features)} features")

    # Map labels to numeric target
    y = df[label_col].map(lambda val: TARGET_MAP.get(str(val).upper(), 0)).values

    X = df[active_features].fillna(0.0).astype(np.float32)

    return X, y, active_features, df


def train_models(X, y, active_features, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    # Stratified Train/Test Split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"\n[+] Dataset Partition:")
    print(f"    - Training Samples: {len(X_train)}")
    print(f"    - Testing Samples : {len(X_test)}")
    unique_classes, counts = np.unique(y_train, return_counts=True)
    for c, cnt in zip(unique_classes, counts):
        print(f"      * Class {c} ({INV_TARGET_MAP[c]}): {cnt} samples")

    # Candidate Models
    candidate_models = {
        "RandomForest": RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=3,
            class_weight="balanced",
            random_state=42
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=100,
            max_depth=8,
            random_state=42
        )
    }

    best_model_name = None
    best_f1 = -1.0
    best_model = None

    print(f"\n--- Training Candidate Classifiers ---")
    for name, clf in candidate_models.items():
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        f1 = f1_score(y_test, preds, average="weighted", zero_division=0)
        acc = accuracy_score(y_test, preds)

        print(f"  * {name:<22} -> Test Accuracy: {acc*100:.2f}% | Weighted F1: {f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_model = clf

    print(f"\n[+] Champion Model Selected: {best_model_name} (F1: {best_f1:.4f})")

    # Detailed Evaluation on Test Set
    test_preds = best_model.predict(X_test)
    print("\n--- Champion Model Classification Report ---")
    target_names = [INV_TARGET_MAP[c] for c in sorted(np.unique(y_test))]
    print(classification_report(y_test, test_preds, target_names=target_names, zero_division=0))

    cm = confusion_matrix(y_test, test_preds)
    print("--- Confusion Matrix ---")
    print(cm)

    # Feature Importance (if Random Forest)
    importance_dict = {}
    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
        sorted_indices = np.argsort(importances)[::-1]
        print("\n--- Top Predictive Features ---")
        for i in sorted_indices[:8]:
            feat = active_features[i]
            score = importances[i]
            importance_dict[feat] = float(score)
            print(f"  {feat:<30} : {score*100:.2f}%")

    # Export Model Bundle compatible with HybridRiskEngine
    bundle = {
        "model": best_model,
        "model_name": best_model_name,
        "feature_cols": active_features,
        "label_map": TARGET_MAP,
        "inv_label_map": INV_TARGET_MAP,
        "f1_score": float(best_f1),
        "feature_importances": importance_dict
    }

    # Save as model.pkl and model_calibrated.pkl
    pkl_path = os.path.join(output_dir, "model.pkl")
    calibrated_pkl_path = os.path.join(output_dir, "model_calibrated.pkl")
    joblib.dump(bundle, pkl_path)
    joblib.dump(bundle, calibrated_pkl_path)
    print(f"\n[SUCCESS] Model Bundle saved to:")
    print(f"  -> {pkl_path}")
    print(f"  -> {calibrated_pkl_path}")

    # Export configuration JSON metadata
    config_metadata = {
        "model_type": best_model_name,
        "target_mapping": INV_TARGET_MAP,
        "active_features": active_features,
        "metrics": {
            "weighted_f1": round(best_f1, 4),
            "test_accuracy": round(accuracy_score(y_test, test_preds), 4)
        },
        "top_features": importance_dict
    }
    json_path = os.path.join(output_dir, "ml_config.json")
    with open(json_path, "w") as f:
        json.dump(config_metadata, f, indent=2)
    print(f"  -> {json_path}\n")

    return best_model


def main():
    parser = argparse.ArgumentParser(description="Train ML models on calibrated dynamic room data.")
    parser.add_argument("--data", "-d", type=str, default="data/processed/smart_fire_dataset_calibrated.csv", help="Calibrated CSV path")
    parser.add_argument("--output-dir", "-o", type=str, default="ml/models/v1", help="Output directory for trained model")
    args = parser.parse_args()

    data_file = args.data
    if not os.path.exists(data_file):
        # Fallback to local
        local_cand = "smart_fire_dataset_calibrated.csv"
        if os.path.exists(local_cand):
            data_file = local_cand
        else:
            print(f"[!] '{data_file}' not found. Running calibration tool on default dataset first...")
            os.system(f"python tools/preprocess_and_calibrate.py --output {data_file}")

    print("==================================================================")
    print(" FIRESHIELD AI — CALIBRATED MULTI-SENSOR ML TRAINING PIPELINE")
    print("==================================================================")
    X, y, active_features, df = prepare_dataset(data_file)
    train_models(X, y, active_features, args.output_dir)


if __name__ == "__main__":
    main()
