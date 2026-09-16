# FireShield AI — Pilot Deployment & Operational Test Plan

**Document:** Pilot Operations Framework  
**Scope:** 3–5 Pilot Nodes over a 30-Day Testing Period  
**Target Environments:** Low-risk, controlled commercial/residential zones  

---

## 1. Pilot Cohort Environments

| Unit ID | Location / Environment | Ambient Risk Factors | Primary Verification Focus |
|---|---|---|---|
| **NODE-01** | Electronics Hardware Workshop | Soldering irons, hot air guns, flux vapors. | False alarm suppression against localized soldering heat. |
| **NODE-02** | Server Rack / Network Closet | High continuous airflow, electrical fire hazard. | Early particulate and thermal rate-of-change detection. |
| **NODE-03** | Residential Kitchen | Cooking vapors, boiling water steam, toaster thermal plumes. | Cross-sensor fusion (distinguishing steam/cooking smoke from true flame). |
| **NODE-04** | Small Warehouse Storage Bay | Ambient temperature swings, dust particulate. | Baseline tracking and long-range optical sweep sensitivity. |
| **NODE-05** | Engineering Benchtop (Reference) | Stationary climate-controlled room. | Uptime baseline, packet loss, and battery degradation tracking. |

---

## 2. Key Performance Indicators (KPIs) & Pass/Fail Gates

| Metric | Target / Gate | Measurement Method |
|---|---:|---|
| **Missed-Fire Rate** | **0.0% (Zero Misses)** | Controlled stimulus trials (IR test lamp at 1m distance, 5 scheduled trials per unit). |
| **False-Alarm Rate** | **< 1.0% of operating days** | Nuisance alarm count during normal everyday operations over 30 days. |
| **Alert Latency** | **< 2.0 seconds** | Time delta from sensor threshold breach to mobile push notification delivery. |
| **Wireless Uptime** | **> 99.5%** | Wi-Fi packet heartbeat reception logged every 10 seconds in backend. |
| **Aiming Accuracy** | **± 10° of true vector** | Verified against laser pointer mounted co-axially on response servo horn. |

---

## 3. Daily Pilot Operational Rhythm
1. **Automated Morning Health Check**: Backend runs daily cron at 08:00 AM verifying all 5 nodes reported within the last 60 seconds and battery voltages are $\ge 3.7\text{V}$.
2. **Weekly Calibration Verification**: Inspect optical lens and MQ-2 sensor mesh for dust accumulation; wipe clean with isopropyl alcohol wipes.
3. **Pilot Feedback Loop**: Any warning or alarm triggers an immediate SMS/Telegram to the pilot lead with a direct link to the Web Ops Fleet Monitor.
