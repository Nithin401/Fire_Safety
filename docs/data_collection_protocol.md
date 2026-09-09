# Data Collection Protocol

## Objective
To collect high-quality, real-world IR flame sensor data without fabricating numbers or assuming thresholds.

## Procedure
1. Flash `firmware/esp1_detection/esp1_detection.ino` to ESP1.
2. Connect the IR flame sensor's AO (Analog Output) to ESP8266 A0.
   - *Warning: Verify module voltage limits before connecting to A0 (which often expects max 3.3V or 1.0V depending on the exact NodeMCU board).*
3. Connect ESP1 to laptop via USB.
4. Run the Python logger:
   ```bash
   python tools/flame_data_logger.py --session NORMAL_001 --condition NORMAL
   ```
5. Perform the experiment (e.g., let it sit in a normal room, or safely ignite a controlled test flame).
6. Press `Ctrl+C` to stop logging.

## Guidelines
- Never mix synthetic data with real data.
- Ensure unique session IDs for every experiment.
- Clearly note the condition (NORMAL, FLAME, RECOVERY, NOISE).
