#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t min_angle;
    uint8_t max_angle;
    int8_t  offset;
    bool    reverse;
} ServoConfig;

/**
 * Maps raw detected angle to calibrated physical aim servo angle.
 */
inline uint8_t map_aim_angle(uint8_t detected_angle, const ServoConfig* config) {
    int16_t mapped = detected_angle;
    
    if (config->reverse) {
        mapped = 180 - mapped;
    }
    
    mapped += config->offset;
    
    if (mapped < config->min_angle) mapped = config->min_angle;
    if (mapped > config->max_angle) mapped = config->max_angle;
    
    return (uint8_t)mapped;
}

/**
 * Checks if response activation should be killed due to comms watchdog timeout.
 * Returns true if timed out (safety interlock: shut off relay immediately).
 */
inline bool check_response_timeout(uint32_t current_time_ms, uint32_t last_packet_time_ms, uint32_t timeout_ms) {
    if (current_time_ms < last_packet_time_ms) {
        // Timer wrapped / overflowed
        return false;
    }
    return ((current_time_ms - last_packet_time_ms) > timeout_ms);
}

#ifdef __cplusplus
}
#endif
