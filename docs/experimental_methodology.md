# Experimental Methodology

## Core Principles
1. **No fabricated data**: All machine learning metrics (accuracy, F1, etc.) must be derived from actual hardware sessions.
2. **Session-level Splitting**: Training and testing sets must be separated by distinct experimental sessions (e.g., Train on `FLAME_001`, `FLAME_002`; Test on `FLAME_003`). Never leak adjacent time-series samples from the same experiment into both sets.
3. **Reproducibility**: Every CSV must contain metadata (distance, orientation, condition) to reproduce the test.

## Execution
- **NORMAL testing**: Collect hours of baseline data to understand sensor drift, daylight IR interference, and electrical noise.
- **FLAME testing**: Perform controlled fire exposures at various distances.
- **RECOVERY testing**: Observe how long the sensor takes to return to baseline after a fire is extinguished.
- **NOISE testing**: Introduce deliberate IR interference (e.g., sunlight, TV remotes, heaters) and label as NOISE to train the system against false positives.
