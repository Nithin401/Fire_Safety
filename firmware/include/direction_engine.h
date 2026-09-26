#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SWEEP_BINS 19  // 0 to 180 degrees in steps of 10 degrees

typedef struct {
    uint16_t sweep_readings[SWEEP_BINS]; // ADC reading at each 10-deg bin
    uint8_t  best_angle;                 // Angle of lowest ADC (peak flame intensity)
    uint16_t min_reading;                // Lowest ADC value found in current sweep
    float    direction_confidence;       // 0.0 to 1.0 based on peak prominence
    bool     sweep_complete;
} DirectionScanState;

inline void init_direction_scanner(DirectionScanState* state) {
    for (int i = 0; i < SWEEP_BINS; ++i) {
        state->sweep_readings[i] = 1023;
    }
    state->best_angle = 90;
    state->min_reading = 1023;
    state->direction_confidence = 0.0f;
    state->sweep_complete = false;
}

/**
 * Record a reading at a specific sweep angle (0 - 180 degrees).
 */
inline void record_sweep_sample(DirectionScanState* state, uint8_t angle, uint16_t flame_raw) {
    if (angle > 180) angle = 180;
    int bin = angle / 10;
    if (bin >= SWEEP_BINS) bin = SWEEP_BINS - 1;
    
    // Store lowest reading seen at this bin
    if (flame_raw < state->sweep_readings[bin]) {
        state->sweep_readings[bin] = flame_raw;
    }
}

/**
 * Computes peak angle and directional prominence confidence after a sweep pass completes.
 */
inline void finalize_sweep_pass(DirectionScanState* state) {
    uint16_t min_val = 1023;
    int min_bin = 9; // default center
    uint32_t sum = 0;
    
    for (int i = 0; i < SWEEP_BINS; ++i) {
        uint16_t val = state->sweep_readings[i];
        sum += val;
        if (val < min_val) {
            min_val = val;
            min_bin = i;
        }
    }
    
    state->min_reading = min_val;
    state->best_angle = (uint8_t)(min_bin * 10);
    
    float mean_val = (float)sum / (float)SWEEP_BINS;
    float peak_drop = mean_val - (float)min_val;
    
    // If entire room is washed in bright light (mean is low) or no flame (min is high),
    // prominence peak_drop will be low.
    // Normalized prominence: peak_drop / 400.0 clamped to [0, 1]
    if (min_val < 500 && peak_drop > 80.0f) {
        float conf = peak_drop / 350.0f;
        state->direction_confidence = (conf > 1.0f) ? 1.0f : conf;
    } else {
        state->direction_confidence = 0.1f;
    }
    
    state->sweep_complete = true;
}

#ifdef __cplusplus
}
#endif
