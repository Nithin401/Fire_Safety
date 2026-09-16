# Milestone 6: Intelligent Direction Detection & Response Report

**Milestone:** M6 — Intelligent Direction Detection & Response  
**Status:** Validated via Simulation & Pure C++ Algorithmic Verification | **AWAITING PHYSICAL SERVO HARNESS MOUNTING**  
**Date:** September 2026  

---

## 1. Executive Summary
Milestone M6 elevates the system from simple omnidirectional detection to **spatially targeted fire response**.
The detection node (ESP1) conducts dynamic 180° sweeps, records optical prominence profiles across angular bins, computes a **Direction Confidence Score**, and transmits the optimal aiming vector to the response node (ESP2).

---

## 2. Directional Peak Algorithm & Confidence Formula

### Sweeping Search Motion
- ESP1 sweep servo continuously pans a 60° field-of-view IR photodiode from 0° to 180° in 10° discretization bins.
- For each angular bin $\theta \in [0, 180]$, the minimum ADC reading (maximum infrared emission) is stored in `DirectionScanState.sweep_readings`.

### Peak Prominence & Confidence Scoring
To prevent wrong aims caused by diffuse ambient lighting (e.g. sunlight or high room temperature):
$$\bar{S} = \frac{1}{N}\sum_{i=1}^N S_i$$
$$\Delta_{peak} = \bar{S} - \min(S)$$

$$\text{DirectionConfidence} = \begin{cases} 
\min\left(1.0, \frac{\Delta_{peak}}{350}\right) & \text{if } \min(S) < 500 \text{ and } \Delta_{peak} > 80 \\
0.1 & \text{otherwise}
\end{cases}$$

- **Focused Flame:** Yields high $\Delta_{peak}$ ($>300$) and $\text{Confidence} > 0.8$, triggering precision aiming.
- **Diffuse Sunlight / Noise:** $\Delta_{peak}$ is low ($<80$), resulting in $\text{Confidence} \le 0.2$, which instructs the response servo to remain centered (90°) or hold position.

---

## 3. Angle Mapping & Mechanical Calibration
On ESP2, the received target angle is calibrated via `firmware/include/response_logic.h`:
$$\theta_{aim} = \text{clamp}\left(\theta_{target} \times (1 - 2 \cdot \text{reverse}) + \text{offset},\ \theta_{min},\ \theta_{max}\right)$$
- `offset`: Accounts for physical horn misalignment.
- `reverse`: Corrects for mirrored servo mounting orientations.
- `SERVO_MIN` (5°) and `SERVO_MAX` (175°): Protect servo gears from physical stalling at mechanical stops.

---

## 4. Verification & Simulation Results
Validated through `tests/test_direction_detection.py`:
1. **Convergence on Virtual Flames:** Verified target convergence within $\pm 10^\circ$ for simulated flame sources at 40°, 90°, and 130°.
2. **Diffuse Light Rejection:** Verified that flat high-intensity lighting drops confidence to $\le 0.2$.
3. **Dropout Failsafe:** Verified that communications interruption mid-sweep triggers the 3,000 ms watchdog failsafe.
