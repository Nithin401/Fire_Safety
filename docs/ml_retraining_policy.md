# FireShield AI — Machine Learning Retraining & Model Lifecycle Policy

**Author:** Applied ML & Embedded AI Team  
**Status:** Operational Policy  

---

## 1. Overview
Fire safety machine learning models require rigorous governance. Models must continuously adapt to real-world sensor degradation, seasonal climate shifts, and novel environmental interference without suffering catastrophic forgetting or introducing safety regressions.

---

## 2. Retraining Triggers

Retraining is strictly event-driven according to three explicit criteria:

### Trigger 1: Real-World Labeled Data Inflow (Volume Trigger)
- **Threshold**: Whenever $\ge 10$ new verified real-world experimental sessions (minimum 1,200 rows) are captured via `tools/flame_data_logger.py` and validated by `ai/data_validation.py`.
- **Action**: Retrain candidate suite (`ml/train.py`) on combined synthetic + real corpus with weighted sampling favoring empirical sessions.

### Trigger 2: Pilot Incident / False Alarm (Safety Trigger)
- **Threshold**: Any false positive (e.g. system alarmed on non-hazardous smoke/light) or false negative (delayed alert during test) occurring during a pilot deployment.
- **Action**:
  1. Isolate the 5-minute pre-incident and post-incident sensor window.
  2. Label the episode and append to the critical edge-case benchmark dataset.
  3. Retrain model with higher penalty weight on the failure class.

### Trigger 3: Sensor Hardware Revision (Hardware Trigger)
- **Threshold**: Any change in photodiode supplier, ADC gain resistor, or transition to new gas sensors (e.g. MQ-2 to digital BME680).
- **Action**: Mandatory full recalibration and fresh baseline collection.

---

## 3. Automated Gating Criteria for Deployment

No newly trained model candidate may be promoted to production (`ml/models/vN/model.pkl` or `.onnx`) unless it satisfies ALL of the following automated gates in `ml/evaluate.py`:

1. **Missed-Fire Rate $\le 0.001\%$** (Zero missed fires allowed on test benchmark).
2. **False-Alarm Rate $\le$ Current Production Model** (Must not regress on false alarms).
3. **Macro F1-Score $\ge 0.95$**.
4. **Deterministic Backstop Interlock Active**: Model must run through `HybridRiskEngine` where rule-based thresholding retains ultimate suppression authority.

---

## 4. Retraining Execution Workflow

```bash
# 1. Validate newly collected real-world CSV logs
python -m ai.data_validation data/real/

# 2. Recompile versioned master dataset
python -m ai.build_processed_dataset --output-dir data/processed/v2 --version 2.0

# 3. Generate feature table
python -m ai.build_features --input data/processed/v2/dataset.parquet --output-dir data/features/v2

# 4. Generate session-separated splits
python -m ml.split --features data/features/v2/features.parquet --output-dir data/features/v2/splits

# 5. Train model suite and export ONNX
python -m ml.train --splits-dir data/features/v2/splits --output-dir ml/models/v2

# 6. Evaluate against safety benchmarks
python -m ml.evaluate
```
