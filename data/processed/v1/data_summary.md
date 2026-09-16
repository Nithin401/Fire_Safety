# FireShield AI — Dataset Summary Report (v1.0)

**Generated At:** 2026-09-16T05:50:09.962049+00:00  
**Total Rows:** 4800  
**Total Sessions:** 40  
**Date Range:** 2026-09-16 05:42:53.260770+00:00 to 2026-09-16 05:44:52.346608+00:00  

---

## 1. Class Distribution

| Ground Truth Label | Sample Count | Percentage |
|---|---:|---:|
| `NORMAL` | 3306 | 68.9% |
| `FIRE` | 1440 | 30.0% |
| `FALSE_ALARM` | 54 | 1.1% |

---

## 2. Sensor Channel Statistics

| Sensor Channel | Min | Mean | Max | Std Dev | Unit |
|---|---:|---:|---:|---:|---|
| `flameRaw` | 140 | 732.2 | 939 | 286.5 | ADC (0-1023) |
| `tempC` | 23.1 | 36.6 | 80.2 | 20.1 | °C |
| `humidity` | 37.7 | 50.6 | 60.0 | 6.2 | % RH |
| `gasRaw` | 103 | 240.4 | 738 | 197.9 | ADC (0-1023) |
| `smokeRaw` | 84 | 242.7 | 752 | 230.2 | ADC (0-1023) |

---

## 3. Data Provenance

| Data Source | Session Count | Row Count |
|---|---:|---:|
| `synthetic` | 40 | 4800 |
| `real` | 0 | 0 |

---

*Verified against schema `docs/dataset_schema.md` with zero schema violations.*
