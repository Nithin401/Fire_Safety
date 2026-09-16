# FireShield AI — Official Dataset Schema (v2.0)

All sensor sessions collected via `tools/flame_data_logger.py` (hardware) or `ai/synthetic_data_generator.py` (simulation) conform to this unified multi-sensor schema.

| Column | Type | Unit / Range | Description | Mandatory |
|---|---|---|---|---|
| `timestamp` | ISO 8601 String | UTC format | Host timestamp when reading was recorded. | Yes |
| `sessionId` | String | e.g. `FIRE_001` | Unique experiment/session identifier. | Yes |
| `deviceId` | String | e.g. `dev_001` | Edge node identifier. | Yes |
| `roomId` | String | e.g. `Kitchen` | Location designation. | Yes |
| `flameRaw` | Integer | 0 – 1023 | 10-bit analog IR flame sensor value (ambient ~850-950, drops on fire). | Yes |
| `tempC` | Float | -20.0 – 120.0 °C | Ambient or fire temperature from DHT22/BME280. | Yes |
| `humidity` | Float | 0.0 – 100.0 % | Relative humidity percentage. | Yes |
| `gasRaw` | Integer | 0 – 1023 | MQ-2 / MQ-135 combustion gas analog reading. | Yes |
| `smokeRaw` | Integer | 0 – 1023 | Particulate smoke analog reading. | Yes |
| `fireAngle` | Integer | 0 – 180 deg | Orientation of detected fire from search servo. | Yes |
| `label` | Categorical | `NORMAL`, `FIRE`, `FALSE_ALARM` | Ground truth condition tag. | Yes |
| `distance_cm` | Integer | >= 0 cm | Distance from sensor node to ignition/stimulus point. | Yes |
| `environment_notes` | String | Text | Operational context (room dimensions, airflow, interference). | No |
| `data_source` | Categorical | `synthetic`, `real` | Explicit tag distinguishing physical datasets from simulated sets. | Yes |

---

### Integrity Constraints
1. **Monotonicity**: Successive rows within a `sessionId` must possess strictly non-decreasing timestamps.
2. **Gap Threshold**: Consecutive packet gaps exceeding 3.0 seconds are flagged as dropped comms.
3. **Range Adherence**: Any values outside ADC boundaries (0–1023) or physical temperature bounds (-20 to 120°C) must be rejected by `ai/data_validation.py`.
4. **Data Immutability**: Files in `data/real/` and `data/synthetic/` are read-only source files. Cleaned and normalized datasets are compiled into `data/processed/vN/` without modifying raw sources.
