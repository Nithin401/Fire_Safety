# AI Architecture (Current Stage)

We are currently building **AI-oriented signal intelligence**, not a black-box neural network.

## Pipeline Flow

1. **Raw Signal**: Analog reading from IR Flame Sensor (`flame_raw`).
2. **Filtering**: Rolling means and medians to remove noise.
3. **Feature Engine**: Calculates signal variance, rate of change (first derivative), and absolute change.
4. **Baseline Model**: Learns the normal environmental state dynamically (e.g., rolling median over a long window).
5. **Anomaly / Risk Engine**: Evaluates deviation from baseline, persistence of the signal, and statistical anomalies (using z-scores or Isolation Forests).
6. **Risk Score**: Outputs a scaled value 0-100.
7. **State Output**: Maps risk score to SAFE, WARNING, HIGH_RISK, or FIRE.

## Distinction
- This is a **rule-based and statistical anomaly detection** system.
- It is **NOT** a trained Supervised Machine Learning classifier yet.
- Future versions will fuse multiple sensors (Temperature, Gas, Humidity) into an Edge ML model.
