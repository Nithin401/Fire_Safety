# Synthetic Data Disclaimer & Validation Policy

> [!WARNING]
> **PROVISIONAL SYNTHETIC DATASET NOTICE**
> The sensor readings located in `data/synthetic/` and any derived models or metrics are generated using physically plausible mathematical simulations (stochastic Gaussian processes, sigmoid thermal curves, and transient optical spikes).
> 
> They are strictly intended for:
> 1. Verifying data ingestion schemas and end-to-end data pipeline integrity.
> 2. Developing, compiling, and testing feature engineering and ML model pipelines.
> 3. Wiring and validating the mobile application and cloud backend interfaces prior to hardware deployment.
> 
> **MANDATORY RE-VALIDATION REQUIREMENT**:
> All performance metrics (accuracy, F1-score, missed-fire rate, and false-alarm rate) derived from synthetic datasets are **provisional**. Before any commercial deployment or safety certification claim, the entire AI/ML model suite MUST be retrained and validated using empirical datasets collected from physical sensors (`data/real/`) under controlled testing protocols.
