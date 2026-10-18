# FireShield AI project rules

## Scope and safety

- This is an experimental prototype, not a certified life-safety system.
- Preserve local hardware detection and ESP-NOW response even when Wi-Fi, Firebase, or ThingSpeak is unavailable.
- Never place service-account credentials, device passwords, or private server keys in firmware, Flutter, browser assets, Git, or logs.
- Load private Python configuration from `secrets/.env`; generate ignored ESP1 headers with `tools/generate_secrets.py`.
- Do not report a flash, Firebase write, push delivery, real-sensor collection, model training, or accuracy unless it was actually run and recorded.

## Current firmware boundary

- `firmware/esp1_detection/` contains several incompatible ESP1 variants. Do not merge or overwrite them.
- The candidate canonical ESP8266 source supplied outside the repository is `C:\Users\Nithinvarma\Downloads\files (4)\fireshield-esp1.ino`.
- Its intended requirements are: flame AO `A0`, smoke DO `GPIO12`, DHT11 `GPIO4`, servo `GPIO14`, flame threshold `600` (lower value means flame), smoke active state `LOW`, 2-second samples, 200 ms ESP-NOW sends, and 16-second ThingSpeak updates.
- Do not change those meanings, polarities, the ESP-NOW struct layout, or the six-field ThingSpeak mapping without explicit approval and a compatibility test.

## Repository workflow

- Work in phases; report files changed and tests actually run, then stop at the approved boundary.
- Keep generated firmware build files and secrets untracked.
- The `docs/` directory is a nested Git working tree with existing changes; do not overwrite its existing files.
