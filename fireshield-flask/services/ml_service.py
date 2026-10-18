from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from config import Config


class MLService:
    """Service for disciplined ML experimentation, label verification, and model evaluation."""

    MODEL_REGISTRY_PATH = Config.DATA_MODELS_DIR / "model_registry.json"
    ALLOWED_LABELS = ["NORMAL", "NUISANCE", "FIRE", "UNKNOWN"]
    MIN_CLASS_SAMPLES = 5  # minimum samples per class for training

    def __init__(self, config: type[Config] = Config):
        self.config = config
        self.config.DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.config.DATA_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def analyze_dataset_for_ml(
        cls,
        df: pd.DataFrame,
        label_column: Optional[str] = "verified_label",
    ) -> Dict[str, Any]:
        """Inspect columns, missing rates, and label distributions without fabricating."""
        total_rows = len(df)
        cols_info = {}
        for col in df.columns:
            missing_count = int(df[col].isnull().sum())
            cols_info[col] = {
                "dtype": str(df[col].dtype),
                "missing_count": missing_count,
                "missing_pct": round(missing_count / total_rows * 100, 2) if total_rows > 0 else 0,
            }

        label_dist: Dict[str, int] = {}
        has_verified_labels = False
        if label_column and label_column in df.columns:
            series = df[label_column].dropna().astype(str).str.upper()
            label_dist = series.value_counts().to_dict()
            valid_classes = [c for c in label_dist if c in ("NORMAL", "NUISANCE", "FIRE")]
            has_verified_labels = len(valid_classes) >= 2

        # Check if hardware rule (field6) exists
        hardware_fire_dist: Dict[str, int] = {}
        if "field6" in df.columns or "fire_status" in df.columns:
            fire_col = "fire_status" if "fire_status" in df.columns else "field6"
            hardware_fire_dist = df[fire_col].value_counts().to_dict()

        return {
            "total_rows": total_rows,
            "columns": cols_info,
            "label_column": label_column,
            "label_distribution": label_dist,
            "has_verified_labels": has_verified_labels,
            "hardware_fire_distribution": hardware_fire_dist,
            "ready_for_supervised_training": has_verified_labels and all(
                label_dist.get(k, 0) >= cls.MIN_CLASS_SAMPLES for k in ("NORMAL", "FIRE")
            ),
        }

    def train_classifier(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        label_col: str = "verified_label",
        model_type: str = "random_forest",
        test_size: float = 0.25,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """Train a supervised classifier only when valid ground-truth labels and sufficient samples exist."""
        # Safeguard 1: Must have label column
        if label_col not in df.columns:
            return {
                "success": False,
                "error": f"Label column '{label_col}' does not exist in dataset. Please add human-verified labels first.",
            }

        # Safeguard 2: Never allow field6 alone as proof of fire without user confirmation
        if label_col in ("field6", "fire_status"):
            return {
                "success": False,
                "error": (
                    "field6 represents the ESP8266 hardware rule triggered state, NOT independently verified ground truth. "
                    "Use a separate verified_label column (e.g. NORMAL, NUISANCE, FIRE) for supervised ML."
                ),
            }

        # Filter valid classes
        clean_df = df.copy()
        clean_df[label_col] = clean_df[label_col].astype(str).str.upper()
        clean_df = clean_df[clean_df[label_col].isin(["NORMAL", "NUISANCE", "FIRE"])]

        # Drop rows with NaNs in features
        valid_features = [f for f in feature_cols if f in clean_df.columns]
        if not valid_features:
            return {
                "success": False,
                "error": "No valid feature columns selected.",
            }

        clean_df = clean_df.dropna(subset=valid_features + [label_col])

        # Safeguard 3: Sample count checks per class
        counts = clean_df[label_col].value_counts()
        for cls_name in ["NORMAL", "FIRE"]:
            if counts.get(cls_name, 0) < self.MIN_CLASS_SAMPLES:
                return {
                    "success": False,
                    "error": (
                        f"Insufficient samples for class '{cls_name}' "
                        f"(found {counts.get(cls_name, 0)}, minimum {self.MIN_CLASS_SAMPLES} required). "
                        "Fire classification cannot be reliably trained on sparse data."
                    ),
                    "class_counts": counts.to_dict(),
                }

        X = clean_df[valid_features]
        y = clean_df[label_col]

        # Train / Test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        if model_type == "logistic_regression":
            clf = LogisticRegression(random_state=random_state, max_iter=1000)
        else:
            clf = RandomForestClassifier(n_estimators=50, random_state=random_state, max_depth=5)

        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        labels_list = sorted(list(np.unique(y)))
        cm = confusion_matrix(y_test, y_pred, labels=labels_list)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, labels=labels_list, zero_division=0
        )

        metrics_per_class = {}
        for idx, lbl in enumerate(labels_list):
            metrics_per_class[lbl] = {
                "precision": round(float(precision[idx]), 3),
                "recall": round(float(recall[idx]), 3),
                "f1_score": round(float(f1[idx]), 3),
                "support": int(support[idx]),
            }

        # Save model
        model_filename = f"model_{model_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.joblib"
        model_path = self.config.DATA_MODELS_DIR / model_filename
        joblib.dump(clf, model_path)

        training_result = {
            "success": True,
            "model_type": model_type,
            "model_file": model_filename,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "features": valid_features,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "labels": labels_list,
            "confusion_matrix": cm.tolist(),
            "metrics_per_class": metrics_per_class,
            "disclaimer": (
                "Supervised fire classifier is an experimental prototype. "
                "It must NEVER suppress or replace the local deterministic hardware alarm."
            ),
        }

        # Update registry
        self._save_to_registry(training_result)
        return training_result

    def _save_to_registry(self, result: Dict[str, Any]) -> None:
        registry = []
        if self.MODEL_REGISTRY_PATH.exists():
            try:
                registry = json.loads(self.MODEL_REGISTRY_PATH.read_text(encoding="utf-8"))
            except Exception:
                registry = []
        registry.append(result)
        self.MODEL_REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")
