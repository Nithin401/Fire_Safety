# FireShield AI — Dataset Summary Report (v{version})

**Generated At:** {generation_time}  
**Total Rows:** {total_rows}  
**Total Sessions:** {total_sessions}  
**Date Range:** {min_date} to {max_date}  

---

## 1. Class Distribution

| Ground Truth Label | Sample Count | Percentage |
|---|---:|---:|
| `NORMAL` | {count_normal} | {pct_normal:.1f}% |
| `FIRE` | {count_fire} | {pct_fire:.1f}% |
| `FALSE_ALARM` | {count_false} | {pct_false:.1f}% |

---

## 2. Sensor Channel Statistics

| Sensor Channel | Min | Mean | Max | Std Dev | Unit |
|---|---:|---:|---:|---:|---|
| `flameRaw` | {flame_min} | {flame_mean:.1f} | {flame_max} | {flame_std:.1f} | ADC (0-1023) |
| `tempC` | {temp_min:.1f} | {temp_mean:.1f} | {temp_max:.1f} | {temp_std:.1f} | °C |
| `humidity` | {hum_min:.1f} | {hum_mean:.1f} | {hum_max:.1f} | {hum_std:.1f} | % RH |
| `gasRaw` | {gas_min} | {gas_mean:.1f} | {gas_max} | {gas_std:.1f} | ADC (0-1023) |
| `smokeRaw` | {smoke_min} | {smoke_mean:.1f} | {smoke_max} | {smoke_std:.1f} | ADC (0-1023) |

---

## 3. Data Provenance

| Data Source | Session Count | Row Count |
|---|---:|---:|
| `synthetic` | {synthetic_sessions} | {synthetic_rows} |
| `real` | {real_sessions} | {real_rows} |

---

*Verified against schema `docs/dataset_schema.md` with zero schema violations.*
