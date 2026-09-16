# FireShield AI — Safety & Compliance Roadmap

**Author:** Technical Co-Founder / Systems Architect  
**Date:** September 2026  
**Document Classification:** Strategic Regulatory & Risk Policy  

---

## 1. Commercial Go-to-Market Strategy: Two-Tier Positioning

> [!IMPORTANT]
> **Strategic GTM Recommendation**:
> Regulators (UL, CE, NFPA) mandate multi-year, million-dollar certification testing for any apparatus that automatically discharges chemical or pressurized extinguishing agents. 
> 
> To launch an investor-backed startup rapidly without insurmountable regulatory friction:
> 1. **Phase 1 (Commercial MVP & Pilots): Position as "Intelligent Multi-Sensor Early Detection & Fleet Alert Platform"**.
>    - Regulatory bar: Standard FCC / CE Part 15 (Radio Frequency & Electromagnetic Compatibility) and UL 62368-1 (Consumer Audio/Video & Information Tech Equipment).
>    - Value Proposition: Eliminates false alarms, pinpoints fire direction, alerts property owners via mobile & dashboard in <1 second.
> 2. **Phase 2 (Enterprise & Industrial Add-on): "Autonomous Suppression Actuation" as an Opt-In Module**.
>    - Only enabled when paired with certified solenoid valves and third-party approved suppression canisters under controlled industrial/agricultural exemptions.

---

## 2. Target Standards Matrix

| Standard | Governing Body | Scope | FireShield AI Compliance Action |
|---|---|---|---|
| **FCC Part 15 Class B** | FCC (USA) | Unintentional RF radiation from 2.4 GHz Wi-Fi & ESP-NOW radios. | Mandatory for hardware sale in US. Use pre-certified ESP32 modules (FCC ID: 2AC7Z-ESPWROOM32). |
| **CE RED (2014/53/EU)** | European Union | Radio equipment directive, health, electrical safety (EN 62368). | Mandatory for EU deployment. Pre-certified RF module reduces lab testing scope. |
| **UL 217 / UL 268** | Underwriters Laboratories | Single/Multi-station smoke alarms & commercial fire alarm systems. | Target for Phase 2 detection certification; requires testing against standardized polyurethane & heptane smoke chambers. |
| **NFPA 72** | National Fire Protection Assoc. | National Fire Alarm and Signaling Code (audible tone decibel levels, backup battery). | Ensure local buzzer meets 85 dBA @ 3 meters requirement and provides 24-hour backup battery standby. |
| **NFPA 13 / 17A / 2001** | National Fire Protection Assoc. | Installation of Sprinkler Systems / Wet Chemical / Clean Agent Extinguishing. | Relevant for suppression actuators; requires professional mechanical engineering sign-off. |

---

## 3. Product Liability & Risk Mitigation Framework
1. **Disclaimer in Terms of Service & Packaging**: The MVP product must be explicitly labeled: *"Supplementary early-warning system. Not a replacement for code-mandated primary fire alarms or professional emergency services."*
2. **Deterministic Hard Safety Backstop**: Never deploy software where machine learning has unmonitored command of high-current relays or valves. A hardware thermal fuse (e.g. 85°C thermal cutoff switch in series with the power rail) ensures physical failsafe disconnection if electronic control fails.
3. **Audit Trail Logging**: Every detection state change, raw sensor burst, and alert acknowledgment is cryptographically timestamped in Cloud Firestore to prove system uptime and signal fidelity for insurance reviews.
