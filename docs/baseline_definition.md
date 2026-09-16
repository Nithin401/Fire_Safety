# FireShield AI — Environmental Baseline Specification

**Milestone:** M4 — Feature Engineering & Baseline Analysis  
**Status:** Validated  

---

## 1. Concept of Dynamic Baseline
In smart fire detection, static hardcoded thresholds are prone to nuisance false alarms caused by:
- Seasonal or diurnal ambient room temperature drift (e.g., 20°C in winter morning to 32°C in summer afternoon).
- Ambient lighting conditions (direct sunlight vs incandescent bulbs shifting IR photodiode resistance).
- Non-hazardous ambient background VOCs / aerosol levels (cooking, cleaning products).

Therefore, FireShield AI defines the **Environmental Baseline** dynamically using session-aware moving window statistics.

---

## 2. Mathematical Definition

### Warm-up Calibration Window ($W_{cal}$)
For any active node, the initial $N$ samples ($N = 20$ samples $\approx 20$ seconds) establish the initial ambient median:
$$\mu_{0} = \text{median}(S_1, S_2, \dots, S_N)$$

### Rolling Median Baseline ($B_t$)
To prevent slow, benign thermal drifts from triggering alarms while insulating the baseline from rapid combustion spikes, the baseline is computed over a rolling median window of size $W = 50$ samples:
$$B_t = \text{median}(S_{t-W+1}, S_{t-W+2}, \dots, S_t)$$

The median is strictly chosen over the arithmetic mean because the median has a breakdown point of $50\%$, meaning an abrupt fire spike will not drag the baseline upward before detection triggers.

### Baseline Deviation ($\Delta_t$)
The immediate signal deviation from the historical norm is:
$$\Delta_t = S_t - B_t$$

### Statistical Z-Score ($Z_t$)
Normalized deviation measured in units of local rolling standard deviation ($\sigma_{long}$ over $W_{long} = 100$ samples):
$$Z_t = \frac{S_t - \bar{S}_{long}}{\sigma_{long} + \epsilon}$$
A reading is flagged as an anomaly when $|Z_t| > 3.0$ ($99.7\%$ Gaussian confidence interval).

---

## 3. Multi-Sensor Fusion Baseline Metrics
1. **Flame Deviation**: $\Delta_{flame} = \text{flameRaw}_t - B_{flame, t}$ (abrupt drop $\Delta_{flame} < -300$ ADC units).
2. **Thermal Rate of Change**: $\frac{d(\text{tempC})}{dt} > 1.0\ ^\circ\text{C/min}$.
3. **Gas Surge Deviation**: $\Delta_{gas} = \text{gasRaw}_t - B_{gas, t} > 150$ ADC units.
4. **Time Since Last Anomaly ($\tau_{anom}$)**: Duration in seconds since the last $|Z_t| > 3.0$ flag was registered.
