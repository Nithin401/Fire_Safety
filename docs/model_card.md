# Model Card: FireShield AI Multi-Sensor Classifier (v1.0)

## Model Details
- **Model Name:** FireShield Random Forest Multi-Sensor Classifier (`ml/models/v1/model.pkl`, `ml/models/v1/model.onnx`)
- **Version:** 1.0
- **Model Architecture:** Balanced Random Forest Classifier (100 estimators, max depth 12)
- **Framework:** Scikit-Learn 1.7.2 / ONNX Runtime 1.23.2
- **Export Format:** Python Joblib Pickle & Standard Open Neural Network Exchange (ONNX Opset 12)

---

## Intended Use & Safety Guardrails
- **Intended Use:** Early fire risk assessment, multi-sensor correlation (Flame IR + DHT22 Temperature + MQ-2 Gas), and false-alarm suppression (distinguishing transient optical noise from true combustion).
- **Prohibited Use:** Direct, un-gated physical suppression actuation.
- **Safety Interlock Architecture:** The model operates as an **Advisory Layer**. Autonomous response hardware (relay extinguisher activation) requires confirmation from the deterministic rule-based safety backstop (`ai/risk_engine_ml.py`).

---

## Training & Validation Data
- **Dataset:** 4,800 time-series samples across 40 independent sessions (`data/processed/v1/dataset.parquet`).
- **Data Source:** Synthetic stochastic multi-sensor simulator (`data_source: synthetic`).
- **Split Methodology:** Group-wise session separation (`ml/split.py`). Zero session overlap between Train (26 sessions), Val (6 sessions), and Test (8 sessions).

---

## Performance Summary (Unseen Test Set)
- **Missed-Fire Rate:** **0.00%** (0 false negatives out of 384 fire frames)
- **False-Alarm Rate:** **0.00%** (0 false positives out of 576 non-fire frames)
- **Macro F1-Score:** **1.0000**
- **Multi-Class ROC-AUC:** **1.0000**

---

## Known Limitations & Retraining Triggers
1. **Synthetic Data Limitation:** Current weights were fitted against physically plausible synthetic data. Real-world sensor aging, soot accumulation, and humidity drift may require fine-tuning.
2. **Retraining Trigger Policy:**
   - Whenever $\ge 5$ new real-world experimental sessions are recorded with `tools/flame_data_logger.py`.
   - Immediately following any observed false alarm or delayed trigger during pilot testing.
   - Upon any modification to sensor hardware or analog pin wiring.
