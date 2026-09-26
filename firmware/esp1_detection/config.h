#ifndef CONFIG_H
#define CONFIG_H

// =====================================================
// DEVICE CONFIGURATION
// =====================================================

#define DEVICE_ID "ESP1"
#define ROOM_ID   "ROOM_1"

// =====================================================
// HARDWARE PINS
// =====================================================

// Use Analog Pin 0 for continuous reading from flame sensor
#define FLAME_SENSOR_PIN A0  

// =====================================================
// SAMPLING CONFIGURATION
// =====================================================

// Interval between data samples in milliseconds
#define SAMPLE_INTERVAL_MS 1000

#endif // CONFIG_H
