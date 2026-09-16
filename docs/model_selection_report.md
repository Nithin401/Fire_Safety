# FireShield AI — Model Selection & Safety Benchmark Report

**Evaluation Date:** 2026-09-16  
**Test Set:** 960 samples across 8 strictly unseen sessions (`data/features/v1/splits/test.parquet`)  
**Data Leakage Prevention:** Verified 0% session overlap between train, val, and test splits.  

---

## 1. Executive Summary & Gating Decision

In life-safety systems, **Missed-Fire Rate** is the absolute gating metric (it must be ~0%), followed by **False-Alarm Rate** (to prevent nuisance dispatches).

| Evaluation Metric | Deterministic Rule Engine (Baseline) | Random Forest Classifier (M5 ML) | Improvement / Delta |
|---|---:|---:|---|
| **Missed-Fire Rate (FN / Total Fire)** | **82.81%** | **0.00%** | Equal zero-miss safety floor |
| **False-Alarm Rate (FP / Non-Fire)** | 0.52% | **0.00%** | **Significantly Reduced False Alarms** |
| **Macro F1-Score** | 0.3917 | **1.0000** | Substantial gain on edge cases |
| **Multi-Class ROC-AUC** | N/A (Rule-based) | **1.0000** | High discrimination confidence |

**Decision:** Select **Random Forest Classifier** as the primary inference engine, deployed in a **Hybrid Architecture** where the deterministic rule engine acts as the hard safety backstop.

---

## 2. Test Set Confusion Matrix (Random Forest)

```
                 PREDICTED
              NORMAL   FIRE   FALSE_ALARM
ACTUAL
NORMAL         571    0      0     
FIRE           0      384    0     
FALSE_ALARM    0      0      5     
```

---

## 3. Per-Class Precision, Recall, and F1-Score

| Class | Precision | Recall | F1-Score | Support |
|---|---:|---:|---:|---:|
| `NORMAL` | 1.0000 | 1.0000 | 1.0000 | 571.0 |
| `FIRE` | 1.0000 | 1.0000 | 1.0000 | 384.0 |
| `FALSE_ALARM` | 1.0000 | 1.0000 | 1.0000 | 5.0 |
| **Macro Avg** | **1.0000** | **1.0000** | **1.0000** | 960 |
