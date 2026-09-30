#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t flame_threshold;       // Threshold below which flame is triggered (ADC drops on flame)
    uint8_t  persistence_required;  // Consecutive cycles required for confirmation
    uint8_t  current_persistence;   // Current consecutive flame counter
    uint32_t sample_count;
} DetectionState;

inline void init_detection_state(DetectionState* state, uint16_t threshold, uint8_t persistence) {
    state->flame_threshold = threshold;
    state->persistence_required = persistence;
    state->current_persistence = 0;
    state->sample_count = 0;
}

/**
 * Process a raw analog flame reading.
 * Returns true if fire is confirmed by persistent threshold violation.
 */
inline bool evaluate_flame_detection(DetectionState* state, uint16_t flame_raw) {
    state->sample_count++;
    if (flame_raw <= state->flame_threshold) {
        if (state->current_persistence < 255) {
            state->current_persistence++;
        }
    } else {
        if (state->current_persistence > 0) {
            state->current_persistence--;
        }
    }
    return (state->current_persistence >= state->persistence_required);
}

/**
 * Calculates prototype risk score (0-100) based on flame ADC reading and persistence.
 */
inline uint8_t calculate_flame_risk_score(uint16_t flame_raw, uint16_t threshold, uint8_t persistence, uint8_t max_persistence) {
    if (flame_raw > threshold) {
        // Safe baseline: low score
        return (uint8_t)(flame_raw > 800 ? 5 : 15);
    }
    // ADC dropped below threshold: scale 50-100 based on persistence and depth of drop
    uint32_t drop_depth = threshold - flame_raw;
    uint32_t drop_score = (drop_depth * 30) / (threshold > 0 ? threshold : 1);
    uint32_t persist_score = (persistence * 20) / (max_persistence > 0 ? max_persistence : 1);
    uint32_t total = 50 + drop_score + persist_score;
    return (uint8_t)(total > 100 ? 100 : total);
}

#ifdef __cplusplus
}
#endif
