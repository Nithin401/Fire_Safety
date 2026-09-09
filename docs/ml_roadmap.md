# Machine Learning Roadmap

## Phase 1: Data Collection & Signal Intelligence (Current)
- Focus: Single IR flame sensor.
- Method: Rule-based, statistical anomaly detection, dynamic baseline.
- Goal: Understand real sensor noise, drift, and signal bounds.
- Output: Initial dataset of REAL labeled CSVs.

## Phase 2: Supervised ML Evaluation
- Focus: Selecting the best algorithm.
- Candidates: Logistic Regression, Decision Tree, Random Forest, SVM.
- Method: Train on extracted features (variance, derivative, persistence) from Phase 1 data.
- Goal: Validate real accuracy, precision, recall, and false-positive rates on held-out test sessions.

## Phase 3: Sensor Fusion & Edge Deployment
- Focus: Adding Temperature (BME280/DHT22), Gas (MQ-2).
- Method: Train a multi-sensor fusion model.
- Goal: Port the winning model to C++ (Edge ML) to run directly on the ESP8266/ESP32.
- Output: Embedded offline fire classifier.

## Phase 4: Cloud Intelligence
- Focus: FireShield AI integration.
- Method: Upload edge inferences and telemetry to the cloud backend.
- Goal: Multi-room intelligence, historical trend analysis, and persistent mobile alerts.
