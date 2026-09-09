# Alerts and Messages

## Desired behavior

When the local detector reaches a confirmed `HIGH_RISK` or `FIRE` state:

1. The ESP32 immediately operates its local buzzer, red LED, and OLED status.
2. When connectivity is available, it publishes telemetry to FireShield AI.
3. FireShield stores an alert event and presents it in the dashboard.
4. A notification delivery adapter sends a message to the configured recipients.
5. Delivery outcome is recorded; failed delivery must be visible and retried according to policy.

Local signaling is independent of steps 2–5.

## Message contract

```text
FIRE ALERT — ACTION REQUIRED
Location: ROOM_2
Risk: 94% (FIRE)
Temperature: 68.4 C
Smoke/gas: high
Flame: detected
Time: 2026-09-07T12:00:00Z
Device: esp32-room-2
```

The wording must identify the alert as an automated prototype assessment until the complete system is validated.

## Delivery adapters

The active FireShield app persists alerts but has no implemented delivery adapter yet. Add exactly one adapter first after selecting and configuring its provider:

| Channel | Suitable use | Required configuration |
|---|---|---|
| Mobile push (FCM) | App users with FireShield installed | Firebase project, app tokens, notification permissions |
| SMS | Critical fallback when data is unavailable | SMS provider account, sender, recipient consent, delivery cost controls |
| WhatsApp | Operational teams | Approved WhatsApp Business provider/template and recipient opt-in |
| Email | Secondary, non-urgent record | SMTP/provider credentials and verified recipients |

Do not log provider secrets or recipient phone numbers. Do not claim a message was delivered merely because an alert was created.

## Required FireShield changes for live delivery

- Add a `notification_deliveries` record with alert ID, channel, recipient reference, provider message ID, status, attempts, and timestamps.
- Add a `NotificationProvider` interface so channel vendors are swappable.
- Trigger delivery only after an alert is committed successfully.
- Implement rate limits, de-duplication, acknowledgement/resolution, retries, and audit logs.
- Protect configuration with role-based access control and encrypted secrets.

These changes belong in the FireShield AI project, not the ESP32 firmware repository. Provider credentials and recipient rules are a required user decision before real messages can be activated.
